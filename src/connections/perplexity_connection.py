import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.perplexity_connection")


class PerplexityConnectionError(Exception):
    """Base exception for Perplexity connection errors"""
    pass


class PerplexityAPIError(PerplexityConnectionError):
    """Raised when Perplexity API returns an error"""
    pass


class PerplexityConfigurationError(PerplexityConnectionError):
    """Raised when there's an issue with Perplexity configuration"""
    pass


class PerplexityConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None
        self.base_url = "https://api.perplexity.ai"

    @property
    def is_llm_provider(self) -> bool:
        return False  # This is a search provider, not an LLM

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Perplexity configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")
            
        return config

    def _get_client(self) -> OpenAI:
        """Get or create Perplexity client"""
        if not self._client:
            api_key = os.getenv("PERPLEXITY_API_KEY")
            if not api_key:
                raise PerplexityConfigurationError("Perplexity API key not found in environment")
            self._client = OpenAI(
                api_key=api_key,
                base_url=self.base_url
            )
        return self._client

    def register_actions(self) -> None:
        """Register available Perplexity actions"""
        self.actions = {
            "search": Action(
                name="search",
                parameters=[
                    ActionParameter("query", True, str, "The search query to process"),
                    ActionParameter("model", False, str, "Model to use for search (defaults to sonar-reasoning-pro)")
                ],
                description="Perform a search query using Perplexity's Sonar API"
            )
        }

    def configure(self) -> bool:
        """Setup Perplexity API configuration"""
        logger.info("\n🔍 PERPLEXITY API SETUP")

        if self.is_configured():
            logger.info("\nPerplexity API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Perplexity API credentials:")
        logger.info("1. Go to https://www.perplexity.ai/settings")
        logger.info("2. Generate a new API key")
        
        api_key = input("\nEnter your Perplexity API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'PERPLEXITY_API_KEY', api_key)
            
            # Test the configuration
            client = self._get_client()
            self.search("test")  # Simple test query
            
            logger.info("\n✅ Perplexity API configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Perplexity API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if not api_key:
                return False

            client = self._get_client()
            self.search("test")  # Quick test query
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def search(self, query: str, model: str = None, **kwargs) -> str:
        """Perform a search query using Perplexity"""
        try:
            client = self._get_client()
            
            # Use configured model if none provided
            if not model:
                model = self.config.get("model", "sonar-reasoning-pro")

            messages = [
                {
                    "role": "system",
                    "content": "You are a search assistant. Please provide detailed and accurate information based on the search query."
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            completion = client.chat.completions.create(
                model=model,
                messages=messages
            )

            return completion.choices[0].message.content
            
        except Exception as e:
            raise PerplexityAPIError(f"Search failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Perplexity action with validation"""
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