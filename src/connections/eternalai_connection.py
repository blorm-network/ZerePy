import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger(__name__)


class EternalAIConnectionError(Exception):
    """Base exception for EternalAI connection errors"""
    pass


class EternalAIConfigurationError(EternalAIConnectionError):
    """Raised when there are configuration/credential issues"""
    pass


class EternalAIAPIError(EternalAIConnectionError):
    """Raised when EternalAI API requests fail"""
    pass


class EternalAIConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate EternalAI configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        # Validate model exists (will be checked in detail during configure)
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available EternalAI actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation")
                ],
                description="Generate text using EternalAI models"
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
                description="List all available EternalAI models"
            )
        }

    def _get_client(self) -> OpenAI:
        """Get or create EternalAI client"""
        if not self._client:
            api_key = os.getenv("EternalAI_API_KEY")
            api_url = os.getenv("EternalAI_API_URL")
            if not api_key:
                raise EternalAIConfigurationError("EternalAI API key not found in environment")
            self._client = OpenAI(api_key=api_key, base_url=api_url)
        return self._client

    def configure(self) -> bool:
        """Sets up EternalAI API authentication"""
        print("\n🤖 EternalAI API SETUP")

        if self.is_configured():
            print("\nEternalAI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        print("\n📝 To get your EternalAI API credentials:")
        print("1. Go to https://eternalai.org/api")
        print("2. Generate an API Key")
        print("3. Use API url as https://api.eternalai.org/v1/")

        api_key = input("\nEnter your EternalAI API key: ")
        api_url = input("\nEnter your EternalAI API url: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'EternalAI_API_KEY', api_key)
            set_key('.env', 'EternalAI_API_URL', api_url)

            # Validate the API key by trying to list models
            client = OpenAI(api_key=api_key, base_url=api_url)
            client.models.list()

            print("\n✅ EternalAI API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        """Check if EternalAI API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('EternalAI_API_KEY')
            api_url = os.getenv('EternalAI_API_URL')
            if not api_key or not api_url:
                return False

            client = OpenAI(api_key=api_key, base_url=api_url)
            client.models.list()
            return True

        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using EternalAI models"""
        try:
            client = self._get_client()

            # Use configured model if none provided
            if not model:
                model = self.config["model"]
            print("model", model)
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            return completion.choices[0].message.content

        except Exception as e:
            raise EternalAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model, **kwargs):
        try:
            client = self._get_client
            try:
                client.models.retrieve(model=model)
                # If we get here, the model exists
                return True
            except Exception:
                return False
        except Exception as e:
            raise EternalAIAPIError(e)

    def list_models(self, **kwargs) -> None:
        """List all available EternalAI models"""
        try:
            client = self._get_client()
            response = client.models.list().data
            #
            fine_tuned_models = [
                model for model in response
                if model.owned_by in ["organization", "user", "organization-owner"]
            ]
            #
            if fine_tuned_models:
                logger.info("\nFINE-TUNED MODELS:")
                for i, model in enumerate(fine_tuned_models):
                    logger.info(f"{i + 1}. {model.id}")

        except Exception as e:
            raise EternalAIAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Twitter action with validation"""
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
