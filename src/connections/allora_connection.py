import logging
from typing import List, Dict, Any, Optional, cast
from dotenv import set_key
from allora_sdk.v2.api_client import AlloraAPIClient, ChainSlug
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import AlloraConfig
from src.types.config import BaseConnectionConfig
import os
import asyncio

logger = logging.getLogger("connections.allora_connection")

class AlloraConnectionError(Exception):
    """Base exception for Allora connection errors"""
    pass

class AlloraConfigurationError(AlloraConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class AlloraAPIError(AlloraConnectionError):
    """Raised when Allora API requests fail"""
    pass

class AlloraConnection(BaseConnection):
    _client: Optional[AlloraAPIClient]
    chain_slug: str
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Allora connection...")
        # Validate config before passing to super
        validated_config = AlloraConfig(**config)
        super().__init__(validated_config)
        
        self._client = None
        self.chain_slug = validated_config.chain_slug

    @property
    def is_llm_provider(self) -> bool:
        return False

    def _get_client(self) -> AlloraAPIClient:
        """Get or create Allora client"""
        if not self._client:
            api_key = os.getenv("ALLORA_API_KEY")
            if not api_key:
                raise AlloraConfigurationError("Allora API key not found in environment")
            self._client = AlloraAPIClient(
                chain_slug=self.chain_slug,
                api_key=api_key
            )
        return self._client

    def register_actions(self) -> None:
        """Register available Allora actions"""
        self.actions = {
            "get-inference": self.get_inference,
            "list-topics": self.list_topics
        }

    async def _make_request_async(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Make async API request with error handling"""
        try:
            client = self._get_client()
            method = getattr(client, method_name)
            response = await method(*args, **kwargs)
            return response
        except Exception as e:
            raise AlloraAPIError(f"API request failed: {str(e)}")

    def _make_request(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Make API request with error handling"""
        try:
            # Create event loop for async calls
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    self._make_request_async(method_name, *args, **kwargs)
                )
                return response
            finally:
                loop.close()
        except Exception as e:
            raise AlloraAPIError(f"API request failed: {str(e)}")

    def get_inference(self, topic_id: int, **kwargs: Any) -> Dict[str, Any]:
        """Get inference from Allora Network for a specific topic"""
        try:
            response = self._make_request('get_inference_by_topic_id', topic_id)
            return {
                "topic_id": topic_id,
                "inference": response.inference_data.network_inference_normalized
            }
        except Exception as e:
            raise AlloraAPIError(f"Failed to get inference: {str(e)}")

    def list_topics(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """List all available Allora Network topics"""
        try:
            response = self._make_request('get_all_topics')
            return cast(List[Dict[str, Any]], response)
        except Exception as e:
            raise AlloraAPIError(f"Failed to list topics: {str(e)}")

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Allora API authentication"""
        print("\n🔮 ALLORA API SETUP")
        
        if self.is_configured():
            print("\nAllora API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        try:
            api_key = kwargs.get("api_key") or input("\nEnter your Allora API key: ").strip()
            if not api_key:
                raise AlloraConfigurationError("API key cannot be empty")

            # Save to .env file
            set_key('.env', 'ALLORA_API_KEY', api_key)
            print("\n✅ Allora API key saved successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Allora configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = AlloraConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Allora configuration: {str(e)}")

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Allora API is configured"""
        api_key = os.getenv("ALLORA_API_KEY")
        if verbose:
            if not api_key:
                logger.info("\n❌ Allora API key not found in environment")
            else:
                logger.info("\n✅ Allora API key found")
        return bool(api_key)

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
