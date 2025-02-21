import logging
import requests
import json
from typing import Dict, Any
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.ollama_connection")


class OllamaConnectionError(Exception):
    """Base exception for Ollama connection errors"""
    pass


class OllamaAPIError(OllamaConnectionError):
    """Raised when Ollama API requests fail"""
    pass


class OllamaConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")  # Default to local Ollama setup

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Ollama configuration from JSON"""
        required_fields = ["base_url", "model"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        if not isinstance(config["base_url"], str):
            raise ValueError("base_url must be a string")
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available Ollama actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation"),
                ],
                description="Generate text using Ollama's running model"
            ),
        }

    def configure(self) -> bool:
        """Setup Ollama connection (minimal configuration required)"""
        logger.info("\n🤖 OLLAMA CONFIGURATION")

        logger.info("\nℹ️ Ensure the Ollama service is running locally or accessible at the specified base URL.")
        response = input(f"Is Ollama accessible at {self.base_url}? (y/n): ")

        if response.lower() != 'y':
            new_url = input("\nEnter the base URL for Ollama (e.g., http://localhost:11434): ")
            self.base_url = new_url

        try:
            # Test connection
            self._test_connection()
            logger.info("\n✅ Ollama connection successfully configured!")
            return True
        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def _test_connection(self) -> None:
        """Test if Ollama is reachable"""
        try:
            url = f"{self.base_url}/v1/models"
            response = requests.get(url)
            if response.status_code != 200:
                raise OllamaAPIError(f"Failed to connect to Ollama: {response.status_code} - {response.text}")
        except Exception as e:
            raise OllamaConnectionError(f"Connection test failed: {e}")

    def is_configured(self, verbose=False) -> bool:
        """Check if Ollama is reachable"""
        try:
            self._test_connection()
            return True
        except Exception as e:
            if verbose:
                logger.error(f"Ollama configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using Ollama API with streaming support"""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": model or self.config["model"],
                "prompt": prompt,
                "system": system_prompt,
            }
            response = requests.post(url, json=payload, stream=True)

            if response.status_code != 200:
                raise OllamaAPIError(f"API error: {response.status_code} - {response.text}")

            # Initialize an empty string to store the complete response
            full_response = ""

            # Process each line of the response as a JSON object
            for line in response.iter_lines():
                if line:
                    try:
                        # Parse the JSON object
                        data = json.loads(line.decode("utf-8"))
                        # Append the "response" field to the full response
                        full_response += data.get("response", "")
                    except json.JSONDecodeError as e:
                        raise OllamaAPIError(f"Failed to parse JSON: {e}")

            return full_response

        except Exception as e:
            raise OllamaAPIError(f"Text generation failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
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
