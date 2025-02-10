import logging
import os
from typing import Dict, Any, Optional, cast, List, Callable
from dotenv import load_dotenv, set_key
from together import Together
from together.types.models import ModelObject, ModelType

from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import TogetherConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.together_ai_connection")

class TogetherAIConnectionError(Exception):
    """Base exception for Together AI connection errors"""
    pass

class TogetherAIConfigurationError(TogetherAIConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class TogetherAIAPIError(TogetherAIConnectionError):
    """Raised when Together AI API requests fail"""
    pass

class TogetherAIConnection(BaseConnection):
    _client: Optional[Together]
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Together AI connection...")
        # Validate config before passing to super
        validated_config = TogetherConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Together AI configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = TogetherConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Together AI configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Together AI actions"""
        self.actions = {
            "generate-text": self.generate_text,
            "check-model": self.check_model,
            "list-models": self.list_models
        }

    def _get_client(self) -> Together:
        """Get or create Together AI client"""
        if not self._client:
            api_key = os.getenv("TOGETHER_API_KEY")
            if not api_key:
                raise TogetherAIConfigurationError("Together API key not found in environment")
            self._client = Together(api_key=api_key)
        return self._client

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Together AI API authentication"""
        logger.info("\n🤖 TOGETHER AI API SETUP")

        if self.is_configured():
            logger.info("\nTogether AI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Together AI API credentials:")
        logger.info("1. Visit https://api.together.ai and sign up or log in.")
        logger.info("2. Navigate to the API Keys section.")
        logger.info("3. Create a new API key or use an existing one.")

        api_key = kwargs.get("api_key") or input("\nEnter your Together AI API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'TOGETHER_API_KEY', api_key)
            
            # Validate the API key by trying to list models
            client = Together(api_key=api_key)
            client.models.list()
            logger.info("\n✅ Together AI API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        """Check if Together AI API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('TOGETHER_API_KEY')
            if not api_key:
                return False

            client = Together(api_key=api_key)
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using Together AI models"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            if not model:
                config = cast(TogetherConfig, self.config)
                model = config.model

            messages = [{"role": "user", "content": prompt},{"role": "system", "content": system_prompt},] 

            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=cast(TogetherConfig, self.config).temperature,
                max_tokens=cast(TogetherConfig, self.config).max_tokens
            )

            return completion.choices[0].message.content
            
        except Exception as e:
            raise TogetherAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
        try:
            client = self._get_client()
            models = client.models.list()
            model_names = model_names = [
                m.id for m in models 
                if m.type in {ModelType.CHAT.value, ModelType.LANGUAGE.value}
            ]
            return model in model_names
        except Exception as e:
            raise TogetherAIAPIError(f"Checking model failed: {e}")

    def list_models(self, **kwargs: Any) -> List[str]:
        """List all available Together AI models"""
        try:
            client = self._get_client()
            models = client.models.list()
            model_list = []
            for model in models:
                if model.type in {ModelType.CHAT.value, ModelType.LANGUAGE.value}:
                    model_list.append(model.id)
                    logger.info(f"{len(model_list)}. {model.id}")
            return model_list

        except Exception as e:
            raise TogetherAIAPIError(f"Listing models failed: {e}")
    
    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
