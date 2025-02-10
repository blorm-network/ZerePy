import logging
import requests
import json
from typing import Dict, Any, Optional, cast
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import OllamaConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.ollama_connection")


class OllamaConnectionError(Exception):
    """Base exception for Ollama connection errors"""
    pass


class OllamaAPIError(OllamaConnectionError):
    """Raised when Ollama API requests fail"""
    pass


class OllamaConnection(BaseConnection):
    base_url: str
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Ollama connection...")
        # Validate config before passing to super
        validated_config = OllamaConfig(**config)
        super().__init__(validated_config)
        self.base_url = validated_config.host  # Use host from config

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Ollama configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = OllamaConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Ollama configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Ollama actions"""
        self.actions = {
            "generate-text": self.generate_text
        }

    def configure(self, **kwargs: Any) -> bool:
        """Setup Ollama connection (minimal configuration required)"""
        logger.info("\n🤖 OLLAMA CONFIGURATION")

        logger.info("\nℹ️ Ensure the Ollama service is running locally or accessible at the specified base URL.")
        response = kwargs.get("response") or input(f"Is Ollama accessible at {self.base_url}? (y/n): ")

        if response.lower() != 'y':
            new_url = kwargs.get("base_url") or input("\nEnter the base URL for Ollama (e.g., http://localhost:11434): ")
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

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using Ollama API with streaming support"""
        try:
            url = f"{self.base_url}/api/generate"
            config = cast(OllamaConfig, self.config)
            payload = {
                "model": model or config.model,
                "prompt": prompt,
                "system": system_prompt,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens if config.max_tokens else None,
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

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an Ollama action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
