import logging
from typing import List, Dict, Any
from dotenv import set_key
from allora_sdk.v2.api_client import AlloraAPIClient, ChainSlug
from src.connections.base_connection import BaseConnection, Action, ActionParameter
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
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None
        self.chain_slug = config.get("chain_slug", ChainSlug.TESTNET)

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
        actions = [
            Action(
                name="get-inference",
                parameters=[
                    ActionParameter("topic_id", True, int, "Topic ID to get inference for")
                ],
                description="Get inference from Allora Network for a specific topic"
            ),
            Action(
                name="list-topics",
                parameters=[],
                description="List all available Allora Network topics"
            )
        ]
        self.actions = {action.name: action for action in actions}

    def _make_request(self, method_name: str, *args, **kwargs) -> Any:
        """Make API request with error handling"""
        try:
            client = self._get_client()
            method = getattr(client, method_name)
            
            # Create event loop for async calls
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(method(*args, **kwargs))
                return response
            finally:
                loop.close()
                
        except Exception as e:
            raise AlloraAPIError(f"API request failed: {str(e)}")

    def get_inference(self, topic_id: int) -> Dict[str, Any]:
        """Get inference from Allora Network for a specific topic"""
        try:
            response = self._make_request('get_inference_by_topic_id', topic_id)
            return {
                "topic_id": topic_id,
                "inference": response.inference_data.network_inference_normalized
            }
        except Exception as e:
            raise AlloraAPIError(f"Failed to get inference: {str(e)}")

    def list_topics(self) -> List[Dict[str, Any]]:
        """List all available Allora Network topics"""
        try:
            return self._make_request('get_all_topics')
        except Exception as e:
            raise AlloraAPIError(f"Failed to list topics: {str(e)}")

    def configure(self) -> bool:
        """Sets up Allora API authentication"""
        print("\n🔮 ALLORA API SETUP")
        
        if self.is_configured():
            print("\nAllora API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        try:
            api_key = input("\nEnter your Allora API key: ").strip()
            if not api_key:
                raise AlloraConfigurationError("API key cannot be empty")

            # Save to .env file
            set_key('.env', 'ALLORA_API_KEY', api_key)
            print("\n✅ Allora API key saved successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Allora configuration from JSON"""
        # No required fields for Allora connection
        return config

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Allora API is configured"""
        api_key = os.getenv("ALLORA_API_KEY")
        if verbose:
            if not api_key:
                logger.info("\n❌ Allora API key not found in environment")
            else:
                logger.info("\n✅ Allora API key found")
        return bool(api_key)

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)