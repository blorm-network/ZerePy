import os
import logging
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.connections.solana_connection import SolanaConnection
import asyncio

logger = logging.getLogger("connections.debridge_connection")

class DeBridgeConnectionError(Exception):
    """Base exception for DeBridge connection errors"""
    pass

class DeBridgeAPIError(DeBridgeConnectionError):
    """Raised when DeBridge API requests fail"""
    pass

class DeBridgeConnection(BaseConnection):

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        load_dotenv()
        self.api_url = os.getenv("DEBRIDGE_API_URL", "https://dln.debridge.finance/v1.0")
        self._session = requests.Session()
        self.solana_connection = None  # Will be set by connection manager

    def set_solana_connection(self, connection: SolanaConnection):
        """Set the Solana connection from the connection manager"""
        self.solana_connection = connection

    def register_actions(self) -> None:
        """Register available DeBridge actions"""
        self.actions = {
            "create_bridge_tx": Action(
                name="create_bridge_tx",
                parameters=[
                    ActionParameter("srcChainId", True, str, "Source chain ID"),
                    ActionParameter("srcChainTokenIn", True, str, "Source token address"),
                    ActionParameter("srcChainTokenInAmount", True, str, "Amount to bridge"),
                    ActionParameter("dstChainId", True, str, "Destination chain ID"),
                    ActionParameter("dstChainTokenOut", True, str, "Destination token address"),
                    ActionParameter("dstChainTokenOutRecipient", True, str, "Destination chain address to receive tokens")
                ],
                description="Create a cross-chain bridging transaction"
            ),
            "execute_bridge_tx": Action(
                name="execute_bridge_tx",
                parameters=[],  # No parameters needed, will use stored tx data
                description="Execute a previously created bridge transaction"
            )
        }

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate DeBridge configuration"""
        if "api_url" not in config:
            config["api_url"] = os.getenv("DEBRIDGE_API_URL", "https://dln.debridge.finance/v1.0")
        return config

    def _get_solana_address(self) -> str:
        """Get Solana wallet public key"""
        wallet = self.solana_connection._get_wallet()
        return str(wallet.pubkey())

    def _make_request(self, method: str, url: str, **kwargs) -> Any:
        """Make HTTP request with error handling"""
        headers = {"accept": "application/json"}
        kwargs['headers'] = headers

        logger.debug(f"Making {method.upper()} request to {url}")
        logger.debug(f"Request params: {kwargs}")
        
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response text: {response.text}")

            try:
                data = response.json()
            except ValueError:
                raise DeBridgeAPIError(f"Invalid response format: {response.text}")

            if not response.ok:
                error_msg = data.get('errorMessage', data.get('message', 'Unknown error occurred'))
                logger.error(f"API error: {error_msg}")
                raise DeBridgeAPIError(f"API error: {error_msg}")

            logger.debug(f"Request successful: {response.status_code}")
            return data

        except requests.Timeout:
            raise DeBridgeAPIError("Request timed out")
            
        except requests.ConnectionError as e:
            raise DeBridgeAPIError(f"Connection error: {str(e)}")
            
        except requests.RequestException as e:
            raise DeBridgeAPIError(str(e))

    def create_bridge_tx(self, srcChainId: str,
                        srcChainTokenIn: str,
                        srcChainTokenInAmount: str,
                        dstChainId: str,
                        dstChainTokenOut: str,
                        dstChainTokenOutRecipient: str,
                        dstChainTokenOutAmount: str = "auto",
                        affiliateFeePercent: str = "0",
                        prependOperatingExpenses: bool = True,
                        skipSolanaRecipientValidation: bool = False) -> Dict[str, Any]:
        """
        Create a cross-chain bridging transaction
        """
        if not dstChainTokenOutRecipient:
            raise DeBridgeConnectionError("dstChainTokenOutRecipient is required")
            
        # Get Solana wallet address for source chain parameters
        solana_address = self._get_solana_address()
        
        params = {
            "srcChainId": srcChainId,
            "srcChainTokenIn": srcChainTokenIn,
            "srcChainTokenInAmount": srcChainTokenInAmount,
            "dstChainId": dstChainId,
            "dstChainTokenOut": dstChainTokenOut,
            "dstChainTokenOutAmount": dstChainTokenOutAmount,
            "affiliateFeePercent": affiliateFeePercent,
            "prependOperatingExpenses": str(prependOperatingExpenses).lower(),
            "skipSolanaRecipientValidation": str(skipSolanaRecipientValidation).lower(),
            "referralCode": "21064",  # Default referral code
            "dstChainTokenOutRecipient": dstChainTokenOutRecipient,  # Required destination address
            "srcChainOrderAuthorityAddress": solana_address,  # Always use source chain address
            "dstChainOrderAuthorityAddress": dstChainTokenOutRecipient  # Use destination address
        }

        result = self._make_request(
            "GET",
            f"{self.api_url}/dln/order/create-tx",
            params=params
        )
        
        # Store the transaction for later execution
        self._last_created_tx = result
        logger.debug(f"Full response from DeBridge: {result}")
        logger.debug(f"Transaction data structure: {result.get('tx', {})}")

        return result

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if DeBridge connection is configured"""
        try:
            # Test API connection by getting supported chains
            response = self._make_request("GET", f"{self.api_url}/supported-chains-info")
            if verbose:
                logger.info("DeBridge connection is configured and working")
            return True
        except Exception as e:
            if verbose:
                logger.error(f"DeBridge connection is not configured or not working: {str(e)}")
            return False

    def configure(self) -> bool:
        """Configure the DeBridge connection"""
        try:
            # Test API connection
            response = self._make_request("GET", f"{self.api_url}/supported-chains-info")
            logger.info("DeBridge API connection successful")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to DeBridge API: {str(e)}")
            return False

    def perform_action(self, action_name: str, kwargs: Dict[str, Any]) -> Any:
        """Execute a DeBridge action with validation"""
        if not self.is_configured():
            raise DeBridgeConnectionError("DeBridge connection is not configured")

        if action_name not in self.actions:
            raise DeBridgeConnectionError(f"Unknown action: {action_name}")

        method_name = action_name
        method = getattr(self, method_name)
        
        # Handle async methods
        if action_name == "execute_bridge_tx":
            return asyncio.run(method(**kwargs))
            
        return method(**kwargs)
