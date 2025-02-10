import logging
import os
from typing import Dict, Any, cast, Optional, List
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import OpenAIConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.openai_connection")

class OpenAIConnectionError(Exception):
    """Base exception for OpenAI connection errors"""
    pass

class OpenAIConfigurationError(OpenAIConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class OpenAIAPIError(OpenAIConnectionError):
    """Raised when OpenAI API requests fail"""
    pass

class OpenAIConnection(BaseConnection):
    _client: Optional[OpenAI]
    
    def __init__(self, config: Dict[str, Any]):
        # Validate config before passing to super
        validated_config = OpenAIConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate OpenAI configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = OpenAIConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid OpenAI configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available OpenAI actions"""
        self.actions = {
            "generate-text": self.generate_text,
            "check-model": self.check_model,
            "list-models": self.list_models
        }

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client"""
        if not self._client:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise OpenAIConfigurationError("OpenAI API key not found in environment")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def configure(self, **kwargs: Any) -> bool:
        """Sets up OpenAI API authentication"""
        logger.info("\n🤖 OPENAI API SETUP")

        if self.is_configured():
            logger.info("\nOpenAI API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your OpenAI API credentials:")
        logger.info("1. Go to https://platform.openai.com/account/api-keys")
        logger.info("2. Create a new project or open an existing one.")
        logger.info("3. In your project settings, navigate to the API keys section and create a new API key")
        
        api_key = kwargs.get("api_key") or input("\nEnter your OpenAI API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'OPENAI_API_KEY', api_key)
            
            # Validate the API key by trying to list models
            client = OpenAI(api_key=api_key)
            client.models.list()

            logger.info("\n✅ OpenAI API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if OpenAI API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                return False

            client = OpenAI(api_key=api_key)
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using OpenAI models"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            if not model:
                model = cast(OpenAIConfig, self.config).model

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            content = completion.choices[0].message.content
            if content is None:
                raise OpenAIAPIError("No content returned from API")
            return content
            
        except Exception as e:
            raise OpenAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs: Any) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                client.models.retrieve(model=model)
                # If we get here, the model exists
                return True
            except Exception:
                return False
        except Exception as e:
            raise OpenAIAPIError(str(e))

    def list_models(self, **kwargs: Any) -> List[str]:
        """List all available OpenAI models"""
        try:
            client = self._get_client()
            response = client.models.list().data
            model_list: List[str] = []
            
            # Filter fine-tuned models
            fine_tuned_models = [
                str(model.id) for model in response 
                if model.owned_by in ["organization", "user", "organization-owner"]
            ]

            gpt_models = [
                "gpt-3.5-turbo",
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini"
            ]
            
            logger.info("\nGPT MODELS:")
            for i, model in enumerate(gpt_models, 1):
                model_list.append(model)
                logger.info(f"{i}. {model}")
            
            if fine_tuned_models:
                logger.info("\nFINE-TUNED MODELS:")
                for i, model_id in enumerate(fine_tuned_models, 1):
                    model_list.append(model_id)
                    logger.info(f"{i}. {model_id}")
            
            return model_list
                    
        except Exception as e:
            raise OpenAIAPIError(f"Listing models failed: {e}")
    
    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
