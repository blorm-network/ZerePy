import logging
import os
from typing import Dict, Any

import requests
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.galadriel_connection")

class GaladrielConnectionError(Exception):
    """Base exception for Galadriel connection errors"""
    pass

class GaladrielConfigurationError(GaladrielConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class GaladrielAPIError(GaladrielConnectionError):
    """Raised when Galadriel API requests fail"""
    pass

API_BASE_URL = "https://api.galadriel.com/v1/verified"

class GaladrielConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Galadriel configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        # Validate model exists (will be checked in detail during configure)
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available Galadriel actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation")
                ],
                description="Generate text using Galadriel models"
            ),
        }

    def _get_client(self) -> OpenAI:
        """Get or create Galadriel client"""
        if not self._client:
            api_key = os.getenv("GALADRIEL_API_KEY")
            if not api_key:
                raise GaladrielConfigurationError("Galadriel API key not found in environment")

            headers = {}
            if fine_tune_api_key := os.getenv("GALADRIEL_FINE_TUNE_API_KEY"):
                headers["Fine-Tune-Authorization"] = f"Bearer {fine_tune_api_key}"
            self._client = OpenAI(api_key=api_key, base_url=API_BASE_URL, default_headers=headers)
        return self._client

    def configure(self) -> bool:
        """Sets up Galadriel API authentication"""
        logger.info("\n🤖 GALADRIEL API SETUP")

        if self.is_configured():
            logger.info("\nGaladriel API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Galadriel API credentials:")
        logger.info("1. Go to https://dashboard.galadriel.com/dashboard/api_keys")
        logger.info("2. Create a new API key.")

        api_key = input("\nEnter your Galadriel API key: ")
        fine_tune_api_key = input("\nEnter your Optional fine-tune API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'GALADRIEL_API_KEY', api_key)
            if fine_tune_api_key:
                set_key('.env', 'GALADRIEL_FINE_TUNE_API_KEY', fine_tune_api_key)

            # Validate the API key by trying to list models
            if not self._is_api_key_valid(api_key):
                logger.error(f"Configuration failed: invalid API key")
                return False

            logger.info("\n✅ Galadriel API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Galadriel API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('GALADRIEL_API_KEY')
            if not api_key:
                return False

            return self._is_api_key_valid(api_key)
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def _is_api_key_valid(self, api_key):
        response = requests.get(
            f"{API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}"
            },
            timeout=10,
        )
        return response.status_code != 401

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using Galadriel models"""
        try:
            client = self._get_client()

            # Use configured model if none provided
            if not model:
                model = self.config["model"]

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            return completion.choices[0].message.content

        except Exception as e:
            raise GaladrielAPIError(f"Text generation failed: {e}")

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
