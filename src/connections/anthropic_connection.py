import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from anthropic import Anthropic, NotFoundError
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.anthropic_connection")

class AnthropicConnectionError(Exception):
    """Base exception for Anthropic connection errors"""
    pass

class AnthropicConfigurationError(AnthropicConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class AnthropicAPIError(AnthropicConnectionError):
    """Raised when Anthropic API requests fail"""
    pass

class AnthropicConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Anthropic configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")
            
        return config

    def register_actions(self) -> None:
        """Register available Anthropic actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation")
                ],
                description="Generate text using Anthropic models"
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
                description="List all available Anthropic models"
            )
        }

    def _get_client(self) -> Anthropic:
        """Get or create Anthropic client"""
        if not self._client:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise AnthropicConfigurationError("Anthropic API key not found in environment")
            self._client = Anthropic(api_key=api_key)
        return self._client

    def configure(self) -> bool:
        """Sets up Anthropic API authentication"""
        logger.info("\n🤖 ANTHROPIC API SETUP")

        if self.is_configured():
            logger.info("\nAnthropic API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Anthropic API credentials:")
        logger.info("1. Go to https://console.anthropic.com/settings/keys")
        logger.info("2. Create a new API key.")
        
        api_key = input("\nEnter your Anthropic API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w', encoding="utf-8") as f:
                    f.write('')

            set_key('.env', 'ANTHROPIC_API_KEY', api_key)
            
            # Validate the API key
            client = Anthropic(api_key=api_key)
            client.models.list()

            logger.info("\n✅ Anthropic API configuration successfully saved!")
            logger.info("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Anthropic API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                return False

            client = Anthropic(api_key=api_key)
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using Anthropic models"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            if not model:
                model = self.config["model"]

            message = client.messages.create(
                model=model,
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            return message.content[0].text
            
        except Exception as e:
            raise AnthropicAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                client.models.retrieve(model_id=model)
                return True
            except NotFoundError:
                logging.error("Model not found.")
                return False
            except Exception as e:
                raise AnthropicAPIError(f"Model check failed: {e}")
                
        except Exception as e:
            raise AnthropicAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs) -> None:
        """List all available Anthropic models"""
        try:
            client = self._get_client()
            response = client.models.list().data
            model_ids = [model.id for model in response]

            logger.info("\nCLAUDE MODELS:")
            for i, model in enumerate(model_ids):
                logger.info(f"{i+1}. {model}")
                
        except Exception as e:
            raise AnthropicAPIError(f"Listing models failed: {e}")

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