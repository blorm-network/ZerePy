import logging
import requests
from typing import Dict, Any
import os
import json
from dotenv import load_dotenv
from .base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.debridge_connection")


class DebridgeConnectionError(Exception):
    """Base exception for Debridge connection errors"""
    pass


class DebridgeConnection(BaseConnection):

    def __init__(self, config: Dict[str, Any], connections: Dict[str, Any]):
        super().__init__(config)
        self.api_url = "https://dln.debridge.finance"
        self._initialize()
        self.pending_tx = None
        self.connections = connections

    def _initialize(self):
        """Initialize Debridge connection"""
        try:
            load_dotenv()
            self.access_key = os.getenv("DEBRIDGE_ACCESS_KEY")
        except Exception as e:
            raise DebridgeConnectionError(
                f"Failed to initialize Debridge connection: {str(e)}")

    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the configuration parameters"""
        return config

    def register_actions(self) -> None:
        self.actions['create-bridge-tx'] = Action(
            name='create-bridge-tx',
            description='Create Bridge TX using Debridge',
            parameters=[
                ActionParameter(name='connection', type=str, required=True, description='Connection name'),
                ActionParameter(name='srcChainId', type=int,
                                required=True, description='Source chain ID'),
                ActionParameter(name='srcChainTokenIn', type=str,
                                required=True, description='Source chain token address'),
                ActionParameter(name='srcChainTokenInAmount', type=str,
                                required=True, description='Amount of source chain token'),
                ActionParameter(name='dstChainId', type=int,
                                required=True, description='Destination chain ID'),
                ActionParameter(name='dstChainTokenOut', type=str, required=True,
                                description='Destination chain token address'),
                ActionParameter(name='dstChainTokenOutRecipient', type=str, required=True,
                                description='Recipient address on destination chain'),
                ActionParameter(name='dstChainTokenOutAmount', type=str,
                                required=False, description='Amount of destination chain token'),
                ActionParameter(name='dstChainOrderAuthorityAddress', type=str, required=False,
                                description='Destination chain order authority address'),
                ActionParameter(name='affiliateFeeRecipient', type=str, required=False,
                                description='Affiliate fee recipient address'),
                ActionParameter(name='prependOperatingExpense', type=bool,
                                required=False, description='Prepend operating expense'),
                ActionParameter(name='dlnHook', type=str, required=False,
                                description='DLN hook'),
                ActionParameter(name='affiliateFeePercent', type=float,
                                required=False, description='Affiliate fee percentage')
            ]
        )
        self.actions['execute-bridge-tx'] = Action(
            name='execute-bridge-tx',
            description='Execute bridge transaction using Debridge',
            parameters=[
                ActionParameter(name='connection', type=str, required=True, description='Connection name'),
                ActionParameter(name='compute_unit_price', type=int, required=False, description='Compute unit price'),
                ActionParameter(name='compute_unit_limit', type=int, required=False, description='Compute unit limit')
            ]
        )
        self.actions['get-order-status'] = Action(
            name='get-order-status',
            description='Get order status using Debridge',
            parameters=[
                ActionParameter(name='id', type=str, required=False, description='Order ID'),
                ActionParameter(name='hash', type=str, required=False, description='Transaction hash')
            ]
        )
        self.actions['get-order-details'] = Action(
            name='get-order-details',
            description='Get order details using Debridge',
            parameters=[
                ActionParameter(name='id', type=str, required=True, description='Order ID')
            ]
        )
        self.actions['cancel-tx'] = Action(
            name='cancel-tx',
            description='Cancel transaction using Debridge',
            parameters=[
                ActionParameter(name='id', type=str, required=True, description='Order ID')
            ]
        )
        self.actions['extcall-cancel-tx'] = Action(
            name='extcall-cancel-tx',
            description='External call to cancel transaction using Debridge',
            parameters=[
                ActionParameter(name='id', type=str, required=True, description='Order ID')
            ]
        )
        self.actions['get-supported-chains'] = Action(
            name='get-supported-chains',
            description='Get supported chains using Debridge',
            parameters=[]
        )
        self.actions['get-token-list'] = Action(
            name='get-token-list',
            description='Get token list using Debridge',
            parameters=[
                ActionParameter(name='chainId', type=int, required=True, description='Chain ID')
            ]
        )

    def configure(self) -> bool:
        """Configure the Debridge connection"""
        try:
            self._initialize()
            return True
        except Exception as e:
            logger.error(f"Failed to configure Debridge connection: {str(e)}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if the connection is properly configured"""
        try:
            if not self.connections:
                logger.error("No connections found")
                return False
            return True
        except Exception as e:
            if verbose:
                logger.error(f"Configuration check failed: {str(e)}")
            return False

    def create_bridge_tx(
            self, 
            connection: str,
            srcChainId: int, 
            srcChainTokenIn: str, 
            dstChainId: int, 
            dstChainTokenOut: str, 
            dstChainTokenOutRecipient: str, 
            dstChainOrderAuthorityAddress: str = None, 
            affiliateFeeRecipient: str = None,
            prependOperatingExpense: bool = True,
            srcChainTokenInAmount: str = "auto",
            dstChainTokenOutAmount: str = "auto", 
            affiliateFeePercent: float = 0,
            dlnHook: str = None
        ) -> Dict:
        """Create Bridge TX using Debridge"""
        try:
            connection_class: BaseConnection = self.connections[connection]
            srcChainOrderAuthorityAddress = connection_class.get_address().split(" ")[-1]
            logger.info(srcChainOrderAuthorityAddress)
            params = {
                "srcChainId": srcChainId,
                "srcChainTokenIn": srcChainTokenIn,
                "srcChainTokenInAmount": srcChainTokenInAmount,
                "dstChainId": dstChainId,
                "dstChainTokenOut": dstChainTokenOut,
                "dstChainTokenOutAmount": dstChainTokenOutAmount,
                "prependOperatingExpense": prependOperatingExpense,
                "dstChainTokenOutRecipient": dstChainTokenOutRecipient,
                "srcChainOrderAuthorityAddress": srcChainOrderAuthorityAddress,
                "dstChainOrderAuthorityAddress": dstChainOrderAuthorityAddress,
                "affiliateFeePercent": affiliateFeePercent,
                "affiliateFeeRecipient": affiliateFeeRecipient,
                "dlnHook": dlnHook,
                "accesstoken": self.access_key,                
                "referralCode": 21064,
                "deBridgeApp": "ZEREPY"

            }

            response = requests.get(f"{self.api_url}/v1.0/dln/order/create-tx", params=params)
            response.raise_for_status()
            data = response.json()
            self.pending_tx = data
            logger.info(json.dumps(data["estimation"], indent=4))

        except Exception as e:
            raise DebridgeConnectionError(f"Failed to bridge assets: {str(e)}")
        
    def execute_bridge_tx(self, connection: str, compute_unit_price: int = 200_000, compute_unit_limit: int = None) -> None:
        """Execute bridge transaction using Debridge"""
        try:
            logger.info("Executing bridge transaction...")
            
            if not self.pending_tx:
                raise ValueError("No pending transaction found")
            
            connection_class: BaseConnection = self.connections[connection]

            if connection == "solana":
                data = {
                    "tx": self.pending_tx["tx"]["data"],
                    "compute_unit_price": compute_unit_price
                }
                if compute_unit_limit:
                    data["compute_unit_limit"] = compute_unit_limit
                tx_url = connection_class.perform_action("send-transaction", data)
            else:
                tx_url = connection_class.perform_action("send-transaction", {
                    "tx": json.dumps({
                        "tx": self.pending_tx["tx"], 
                        "estimation": self.pending_tx["estimation"]
                    })
                })

            self.pending_tx = None
            return tx_url

        except Exception as e:
            raise DebridgeConnectionError(f"Failed to execute bridge transaction: {str(e)}")

    def get_order_status(self, id: str = None, hash: str = None) -> Dict:
        """Get order status using Debridge"""
        try:
            if (id):
                response = requests.get(f"{self.api_url}/v1.0/dln/order/{id}/status", params={"accesstoken": self.access_key})
            elif (hash):
                response = requests.get(f"{self.api_url}/v1.0/dln/tx/{hash}/order-ids", params={"accesstoken": self.access_key})
            else:
                raise ValueError("Either 'id' or 'hash' must be provided")
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to get order status: {str(e)}")

    def get_order_details(self, id: str) -> Dict:
        """Get order details using Debridge"""
        try:
            response = requests.get(f"{self.api_url}/v1.0/dln/order/{id}", params={"accesstoken": self.access_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to get order details: {str(e)}")

    def cancel_tx(self, id: str) -> Dict:
        """Cancel transaction using Debridge"""
        try:
            response = requests.post(f"{self.api_url}/v1.0/dln/order/{id}/cancel-tx", params={"accesstoken": self.access_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to cancel transaction: {str(e)}")

    def extcall_cancel_tx(self, id: str) -> Dict:
        """External call to cancel transaction using Debridge"""
        try:
            response = requests.post(f"{self.api_url}/v1.0/dln/order/{id}/extcall-cancel-tx", params={"accesstoken": self.access_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to perform external call to cancel transaction: {str(e)}")

    def get_supported_chains(self) -> Dict:
        """Get supported chains using Debridge"""
        try:
            response = requests.get(f"{self.api_url}/v1.0/supported-chains-info", params={"accesstoken": self.access_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to get supported chains: {str(e)}")

    def get_token_list(self, chainId: int) -> Dict:
        """Get token list using Debridge"""
        try:
            response = requests.get(f"{self.api_url}/v1.0/token-list", params={"chainId": chainId, "accesstoken": self.access_key})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise DebridgeConnectionError(f"Failed to get token list: {str(e)}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Debridge action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        if not self.is_configured(verbose=True):
            raise DebridgeConnectionError(
                "Debridge is not properly configured")

        action = self.actions[action_name]
        validation_errors = action.validate_params(kwargs)
        if validation_errors:
            raise DebridgeConnectionError(
                f"Invalid parameters: {', '.join(validation_errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
