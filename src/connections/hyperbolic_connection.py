import logging
import os
from typing import Dict, Any, Optional, cast, List
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import HyperbolicConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.hyperbolic_connection")

class HyperbolicConnectionError(Exception):
    """Base exception for Hyperbolic connection errors"""
    pass

class HyperbolicConfigurationError(HyperbolicConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class HyperbolicAPIError(HyperbolicConnectionError):
    """Raised when Hyperbolic API requests fail"""
    pass

class HyperbolicConnection(BaseConnection):
    _client: Optional[OpenAI]
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Hyperbolic connection...")
        # Validate config before passing to super
        validated_config = HyperbolicConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Hyperbolic configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = HyperbolicConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Hyperbolic configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Hyperbolic actions"""
        self.actions = {
            "generate-text": self.generate_text,
            "check-model": self.check_model,
            "list-models": self.list_models
        }

    def _get_client(self) -> OpenAI:
        """Get or create Hyperbolic client"""
        if not self._client:
            api_key = os.getenv("HYPERBOLIC_API_KEY")
            if not api_key:
                raise HyperbolicConfigurationError("Hyperbolic API key not found in environment")
            config = cast(HyperbolicConfig, self.config)
            self._client = OpenAI(
                api_key=api_key,
                base_url=config.base_url or "https://api.hyperbolic.xyz/v1"
            )
        return self._client

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Hyperbolic API authentication"""
        logger.info("\n🤖 HYPERBOLIC API SETUP")

        if self.is_configured():
            logger.info("\nHyperbolic API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Hyperbolic API credentials:")
        logger.info("1. Go to https://app.hyperbolic.xyz")
        logger.info("2. Log in with your method of choice")
        logger.info("3. Verify your email address")
        logger.info("4. Generate an API key")
        
        api_key = kwargs.get("api_key") or input("\nEnter your Hyperbolic API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'HYPERBOLIC_API_KEY', api_key)
            
            # Validate the API key by trying to list models
            config = cast(HyperbolicConfig, self.config)
            client = OpenAI(
                api_key=api_key,
                base_url=config.base_url or "https://api.hyperbolic.xyz/v1"
            )
            client.models.list()

            logger.info("\n✅ Hyperbolic API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Hyperbolic API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('HYPERBOLIC_API_KEY')
            if not api_key:
                return False

            config = cast(HyperbolicConfig, self.config)
            client = OpenAI(
                api_key=api_key,
                base_url=config.base_url or "https://api.hyperbolic.xyz/v1"
            )
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using Hyperbolic models"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            config = cast(HyperbolicConfig, self.config)
            if not model:
                model = config.model

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens if config.max_tokens else None,
                top_p=config.top_p,
                presence_penalty=config.presence_penalty,
                frequency_penalty=config.frequency_penalty
            )

            content = completion.choices[0].message.content
            if content is None:
                raise HyperbolicAPIError("No content returned from API")
            return content
            
        except Exception as e:
            raise HyperbolicAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs: Any) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                models = client.models.list()
                for hyperbolic_model in models.data:
                    if hyperbolic_model.id == model:
                        return True
                return False
            except Exception as e:
                raise HyperbolicAPIError(f"Model check failed: {e}")
                
        except Exception as e:
            raise HyperbolicAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs: Any) -> List[str]:
        """List all available Hyperbolic models"""
        try:
            client = self._get_client()
            response = client.models.list().data
        
            model_list: List[str] = []
            for model in response:
                model_list.append(str(model.id))

            logger.info("\nAVAILABLE MODELS:")
            for i, model_id in enumerate(model_list, start=1):
                logger.info(f"{i}. {model_id}")
            
            return model_list
                    
        except Exception as e:
            raise HyperbolicAPIError(f"Listing models failed: {e}")
    
    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute a Hyperbolic action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Explicitly reload environment variables
        load_dotenv()
        
        if not self.is_configured(verbose=True):
            raise HyperbolicConfigurationError("Hyperbolic is not properly configured")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
