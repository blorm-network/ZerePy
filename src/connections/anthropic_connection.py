import logging
import os
from typing import Dict, Any, Optional, cast, List, Union
from dotenv import load_dotenv, set_key
from anthropic import Anthropic, NotFoundError
from anthropic.types import TextBlock, ToolUseBlock
from src.connections.base_connection import BaseConnection
from src.types.connections import AnthropicConfig
from src.types.config import BaseConnectionConfig

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
    _client: Optional[Anthropic]
    
    def __init__(self, config: Dict[str, Any]):
        # Validate config before passing to super
        validated_config = AnthropicConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Anthropic configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = AnthropicConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Anthropic configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Anthropic actions"""
        self.actions = {
            "generate-text": self.generate_text,
            "check-model": self.check_model,
            "list-models": self.list_models
        }

    def _get_client(self) -> Anthropic:
        """Get or create Anthropic client"""
        if not self._client:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise AnthropicConfigurationError("Anthropic API key not found in environment")
            self._client = Anthropic(api_key=api_key)
        return self._client

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Anthropic API authentication"""
        logger.info("\n🤖 ANTHROPIC API SETUP")

        if self.is_configured():
            logger.info("\nAnthropic API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Anthropic API credentials:")
        logger.info("1. Go to https://console.anthropic.com/settings/keys")
        logger.info("2. Create a new API key.")
        
        api_key = kwargs.get("api_key") or input("\nEnter your Anthropic API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
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

    def is_configured(self, verbose: bool = False) -> bool:
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

    def generate_text(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate text using Anthropic models"""
        try:
            client = self._get_client()
            config = cast(AnthropicConfig, self.config)
            
            # Use configured model if none provided
            if not model:
                model = config.model

            message = client.messages.create(
                model=model,
                max_tokens=config.max_tokens or 1000,
                temperature=config.temperature,
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

            content = message.content[0]
            if isinstance(content, TextBlock):
                if content.text is None:
                    raise AnthropicAPIError("No text content returned from API")
                return content.text
            else:
                raise AnthropicAPIError("Unexpected content type returned from API")
            
        except Exception as e:
            raise AnthropicAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs: Any) -> bool:
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

    def list_models(self, **kwargs: Any) -> List[str]:
        """List all available Anthropic models"""
        try:
            client = self._get_client()
            response = client.models.list().data
            model_list: List[str] = []
            for model in response:
                model_list.append(str(model.id))

            logger.info("\nCLAUDE MODELS:")
            for i, model_id in enumerate(model_list, start=1):
                logger.info(f"{i}. {model_id}")
            
            return model_list
                
        except Exception as e:
            raise AnthropicAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
