import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from mira_network import MiraSyncClient
from src.connections.base_connection import BaseConnection, Action, ActionParameter
import asyncio


logger = logging.getLogger("connections.mira_connection")

class MiraConnectionError(Exception):
    """Base exception for Mira connection errors"""
    pass

class MiraConfigurationError(MiraConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class MiraAPIError(MiraConnectionError):
    """Raised when Mira API requests fail"""
    pass

class DictWithModelDump(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow attribute access to dictionary items
        for key, value in self.items():
            setattr(self, key, value)

    def model_dump(self):
        return dict(self)

class MiraConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Mira configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available Mira actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation"),
                ],
                description="Generate text using Mira models"
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
                description="List all available Mira models"
            )
        }

    def _get_client(self) -> MiraSyncClient:
        """Get or create Mira client"""
        if not self._client:
            api_key = os.getenv("MIRA_API_KEY")
            if not api_key:
                raise MiraConfigurationError("Mira API key not found in environment")
            self._client = MiraSyncClient(
                base_url="https://apis.mira.network",
                api_key=api_key
            )
        return self._client

    def configure(self) -> bool:
        """Sets up Mira API authentication"""
        logger.info("\n🤖 MIRA API SETUP")

        if self.is_configured():
            logger.info("\nMira API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Mira API credentials:")
        logger.info("Go to https://mira-network.com")

        api_key = input("\nEnter your Mira API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'MIRA_API_KEY', api_key)

            # Validate the API key by trying to list models
            client = MiraSyncClient(
                api_key=api_key,
                base_url="https://apis.mira.network"
            )
            client.list_models()

            logger.info("\n✅ Mira API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Mira API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('MIRA_API_KEY')
            if not api_key:
                return False

            client = MiraSyncClient(
                api_key=api_key,
                base_url="https://apis.mira.network"
            )
            client.list_models()
            return True

        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using Mira models"""
        try:
            client = self._get_client()

            # Use configured model if none provided
            if not model:
                model = self.config["model"]

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            logger.info(f"Generating text with model: {model}")

            # Create request using our custom dict class that has model_dump
            request = DictWithModelDump({
                "model": model,
                "messages": messages,
                "stream": False
            })
            response = client.generate(request)

            return response["choices"][0]["message"]["content"]

        except Exception as e:
            raise MiraAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                models = client.list_models()
                # Extract model IDs from the response structure
                model_ids = [model['id'] for model in models['data']]
                return model in model_ids
            except Exception as e:
                raise MiraAPIError(f"Model check failed: {e}")

        except Exception as e:
            raise MiraAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs) -> list:
        """List all available Mira models"""
        try:
            client = self._get_client()
            response = client.list_models()

            # Extract just the model IDs from the response
            models = [model['id'] for model in response['data']]

            logger.info("\nAVAILABLE MODELS:")
            for i, model_id in enumerate(models, start=1):
                logger.info(f"{i}. {model_id}")

            return models

        except Exception as e:
            raise MiraAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Mira action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Explicitly reload environment variables
        load_dotenv()

        if not self.is_configured(verbose=True):
            raise MiraConfigurationError("Mira is not properly configured")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)

        # If the method is a coroutine, create a new event loop if none exists
        if asyncio.iscoroutinefunction(method):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(method(**kwargs))

        return method(**kwargs)
