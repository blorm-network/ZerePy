import logging
import os
from typing import Dict, Any
from openai import OpenAI
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter

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
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate XAI configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")
            
        return config

    def register_actions(self) -> None:
        """Register available XAI actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", False, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation")
                ],
                description="Generate text using XAI models"
            ),
            "check-model": Action(
                name="check-model",
                parameters=[
                    ActionParameter("model", True, str, "Model name to check availability")
                ],
                description="Check if a specific model is available"
            ),
            "list-models": Action(
                name="list-models",
                parameters=[],
                description="List all available XAI models"
            )
        }

    def _get_client(self) -> OpenAI:
        """Get or create XAI client using OpenAI's client with custom base URL"""
        if not self._client:
            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                raise XAIConfigurationError("XAI API key not found in environment")
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1",
            )
        return self._client

    def configure(self) -> bool:
        """Sets up XAI API authentication"""
        logger.info("\n🤖 XAI API SETUP")

        if self.is_configured():
            logger.info("\n XAI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your XAI API credentials:")
        logger.info("1. Go to the XAI developer portal (assuming one exists)")
        logger.info("2. Create a new API key for your project.")
        
        api_key = input("\nEnter your XAI API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'XAI_API_KEY', api_key)
            
            # Validate the API key by trying to list models
            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            client.models.list()

            logger.info("\n✅ XAI API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
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

    def generate_text(self, prompt: str, system_prompt: str = None, model: str = None, **kwargs) -> str:
        """Generate text using XAI models"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            if not model:
                model = self.config["model"]

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt} if system_prompt else {"role": "system", "content": ""},
                    {"role": "user", "content": prompt},
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            raise XAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
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

    def list_models(self, **kwargs) -> None:
        """List all available XAI models"""
        try:
            client = self._get_client()
            models = client.models.list().data
            
            logger.info("\nGROK MODELS:")
            for i, model in enumerate(models):
                logger.info(f"{i+1}. {model.id}")
                
        except Exception as e:
            raise XAIAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
