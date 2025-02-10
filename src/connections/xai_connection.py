import logging
import os
from typing import Dict, Any, Optional, cast, List
from openai import OpenAI
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import XAIConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.XAI_connection")

class XAIConnectionError(Exception):
    """Base exception for XAI connection errors"""
    pass

class XAIConfigurationError(XAIConnectionError):
    """Raised when there are configuration/credential issues with XAI"""
    pass

class XAIAPIError(XAIConnectionError):
    """Raised when XAI API requests fail"""
    pass

class XAIConnection(BaseConnection):
    _client: Optional[OpenAI]
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing XAI connection...")
        # Validate config before passing to super
        validated_config = XAIConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate XAI configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = XAIConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid XAI configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available XAI actions"""
        self.actions = {
            "generate-text": self.generate_text,
            "check-model": self.check_model,
            "list-models": self.list_models
        }

    def _get_client(self) -> OpenAI:
        """Get or create XAI client using OpenAI's client with custom base URL"""
        if not self._client:
            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                raise XAIConfigurationError("XAI API key not found in environment")
            config = cast(XAIConfig, self.config)
            self._client = OpenAI(
                api_key=api_key,
                base_url=config.base_url,
            )
        return self._client

    def configure(self, **kwargs: Any) -> bool:
        """Sets up XAI API authentication"""
        logger.info("\n🤖 XAI API SETUP")

        if self.is_configured():
            logger.info("\n XAI API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your XAI API credentials:")
        logger.info("1. Go to the XAI developer portal (assuming one exists)")
        logger.info("2. Create a new API key for your project.")
        
        api_key = kwargs.get("api_key") or input("\nEnter your XAI API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'XAI_API_KEY', api_key)
            
            # Validate the API key by trying to list models
            config = cast(XAIConfig, self.config)
            client = OpenAI(api_key=api_key, base_url=config.base_url)
            client.models.list()

            logger.info("\n✅ XAI API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if XAI API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('XAI_API_KEY')
            if not api_key:
                return False

            client = self._get_client()
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using XAI models"""
        try:
            client = self._get_client()
            config = cast(XAIConfig, self.config)
            
            # Use configured model if none provided
            if not model:
                model = config.model

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt or ""},
                    {"role": "user", "content": prompt},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens if config.max_tokens else None,
                top_p=config.top_p,
                presence_penalty=config.presence_penalty,
                frequency_penalty=config.frequency_penalty
            )
            content = response.choices[0].message.content
            if content is None:
                raise XAIAPIError("No content returned from API")
            return content
            
        except Exception as e:
            raise XAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs: Any) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                client.models.retrieve(model=model)
                return True
            except Exception:
                return False
        except Exception as e:
            raise XAIAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs: Any) -> List[str]:
        """List all available XAI models"""
        try:
            client = self._get_client()
            models = client.models.list().data
            model_list: List[str] = []
            
            logger.info("\nGROK MODELS:")
            for i, model in enumerate(models):
                model_list.append(model.id)
                logger.info(f"{i+1}. {model.id}")
            
            return model_list
                
        except Exception as e:
            raise XAIAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
