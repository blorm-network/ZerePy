import logging
import os
import requests
import time
from typing import Dict, Any, Optional, cast, Union, TypeGuard
from typing_extensions import TypeGuard
from dotenv import load_dotenv, set_key
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.types import Wei, TxParams, TxReceipt, HexBytes
from src.constants.abi import ERC20_ABI
from src.connections.base_connection import BaseConnection
from src.constants.networks import SONIC_NETWORKS
from src.types.connections import SonicConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.sonic_connection")


class SonicConnectionError(Exception):
    """Base exception for Sonic connection errors"""
    pass

class SonicConnection(BaseConnection):
    _web3: Optional[Web3]
    explorer: str
    rpc_url: str
    ERC20_ABI: Any
    NATIVE_TOKEN: str
    aggregator_api: str
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Sonic connection...")
        # Validate config before passing to super
        validated_config = SonicConfig(**config)
        super().__init__(validated_config)
        
        self._web3 = None
        
        # Get network configuration
        network = validated_config.network
        if network not in SONIC_NETWORKS:
            raise ValueError(f"Invalid network '{network}'. Must be one of: {', '.join(SONIC_NETWORKS.keys())}")
            
        network_config = SONIC_NETWORKS[network]
        self.explorer = validated_config.explorer_url or network_config["scanner_url"]
        self.rpc_url = validated_config.rpc_url or network_config["rpc_url"]
        
        self._initialize_web3()
        self.ERC20_ABI = ERC20_ABI
        self.NATIVE_TOKEN = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        self.aggregator_api = validated_config.aggregator_api

    def _get_explorer_link(self, tx_hash: str) -> str:
        """Generate block explorer link for transaction"""
        return f"{self.explorer}/tx/{tx_hash}"

    def _initialize_web3(self) -> None:
        """Initialize Web3 connection"""
        if not self._web3:
            self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Failed to connect to Sonic network")
            
            try:
                chain_id = web3.eth.chain_id
                logger.info(f"Connected to network with chain ID: {chain_id}")
            except Exception as e:
                logger.warning(f"Could not get chain ID: {e}")

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Sonic configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = SonicConfig(**config)
            
            # Additional validation for network
            if validated_config.network not in SONIC_NETWORKS:
                raise ValueError(f"Invalid network '{validated_config.network}'. Must be one of: {', '.join(SONIC_NETWORKS.keys())}")
            
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Sonic configuration: {str(e)}")

    def get_token_by_ticker(self, ticker: str) -> Optional[str]:
        """Get token address by ticker symbol"""
        try:
            if ticker.lower() in ["s", "S"]:
                return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
                
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/search?q={ticker}"
            )
            response.raise_for_status()

            data = response.json()
            if not data.get('pairs'):
                return None

            sonic_pairs = [
                pair for pair in data["pairs"] if pair.get("chainId") == "sonic"
            ]
            sonic_pairs.sort(key=lambda x: x.get("fdv", 0), reverse=True)

            sonic_pairs = [
                pair
                for pair in sonic_pairs
                if pair.get("baseToken", {}).get("symbol", "").lower() == ticker.lower()
            ]

            if sonic_pairs:
                address = sonic_pairs[0].get("baseToken", {}).get("address")
                return str(address) if address is not None else None
            return None

        except Exception as error:
            logger.error(f"Error fetching token address: {str(error)}")
            return None

    def register_actions(self) -> None:
        """Register available Sonic actions"""
        self.actions = {
            "get-token-by-ticker": self.get_token_by_ticker,
            "get-balance": self.get_balance,
            "transfer": self.transfer,
            "swap": self.swap
        }

    def configure(self, **kwargs: Any) -> bool:
        """Configure Sonic connection with private key"""
        logger.info("\n🔷 SONIC CHAIN SETUP")
        if self.is_configured():
            logger.info("Sonic connection is already configured")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            private_key = kwargs.get("private_key") or input("\nEnter your wallet private key: ")
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            set_key('.env', 'SONIC_PRIVATE_KEY', private_key)

            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Failed to connect to Sonic network")

            account = web3.eth.account.from_key(private_key)
            logger.info(f"\n✅ Successfully connected with address: {account.address}")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def _is_web3_instance(self, web3: Any) -> TypeGuard[Web3]:
        """Type guard to check if an object is a valid Web3 instance"""
        return isinstance(web3, Web3) and hasattr(web3, 'is_connected') and hasattr(web3, 'eth')

    def _get_web3(self, verbose: bool = False) -> Optional[Web3]:
        """Get a validated Web3 instance if available"""
        web3 = self._web3
        if web3 is None:
            if verbose:
                logger.error("Web3 not initialized")
            return None

        if not isinstance(web3, Web3):
            if verbose:
                logger.error("Invalid Web3 instance")
            return None

        # At this point, mypy knows web3 is a Web3 instance
        web3_instance: Web3 = web3

        try:
            if not web3_instance.is_connected():
                if verbose:
                    logger.error("Not connected to Sonic network")
                return None

            return web3_instance
        except Exception as e:
            if verbose:
                logger.error(f"Failed to check connection: {e}")
            return None

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if the connection is properly configured"""
        try:
            load_dotenv()
            if not os.getenv('SONIC_PRIVATE_KEY'):
                if verbose:
                    logger.error("Missing SONIC_PRIVATE_KEY in .env")
                return False

            return self._get_web3(verbose) is not None

            return True

        except Exception as e:
            if verbose:
                logger.error(f"Configuration check failed: {e}")
            return False

    def get_balance(self, address: Optional[str] = None, token_address: Optional[str] = None) -> float:
        """Get balance for an address or the configured wallet"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            if not address:
                private_key = os.getenv('SONIC_PRIVATE_KEY')
                if not private_key:
                    raise SonicConnectionError("No wallet configured")
                account = web3.eth.account.from_key(private_key)
                address = account.address

            if not isinstance(address, str):
                raise ValueError("Address must be a string")

            checksum_address = Web3.to_checksum_address(address)

            if token_address:
                contract = web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=self.ERC20_ABI
                )
                balance = contract.functions.balanceOf(checksum_address).call()
                decimals = contract.functions.decimals().call()
                return float(int(balance) / (10 ** decimals))
            else:
                balance = web3.eth.get_balance(checksum_address)
                wei_balance = Wei(balance)
                return float(web3.from_wei(wei_balance, 'ether'))

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            raise

    def transfer(self, to_address: str, amount: float, token_address: Optional[str] = None) -> str:
        """Transfer $S or tokens to an address"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            private_key = os.getenv('SONIC_PRIVATE_KEY')
            if not private_key:
                raise SonicConnectionError("No wallet configured")

            account = web3.eth.account.from_key(private_key)
            chain_id = web3.eth.chain_id
            
            if token_address:
                contract = web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=self.ERC20_ABI
                )
                decimals = contract.functions.decimals().call()
                amount_raw = Wei(int(amount * (10 ** decimals)))
                
                base_tx: TxParams = {
                    'from': account.address,
                    'nonce': web3.eth.get_transaction_count(account.address),
                    'gasPrice': web3.eth.gas_price,
                    'chainId': chain_id
                }
                
                token_tx = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    amount_raw
                ).build_transaction(base_tx)
                tx_to_sign = token_tx
            else:
                native_tx: TxParams = {
                    'nonce': web3.eth.get_transaction_count(account.address),
                    'to': Web3.to_checksum_address(to_address),
                    'value': Wei(web3.to_wei(amount, 'ether')),
                    'gas': 21000,
                    'gasPrice': web3.eth.gas_price,
                    'chainId': chain_id
                }
                tx_to_sign = native_tx

            signed = account.sign_transaction(tx_to_sign)
            tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

            # Wait for transaction receipt and check status
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if not receipt or receipt.get('status') != 1:
                raise SonicConnectionError("Transfer transaction failed")

            # Return explorer link
            tx_link = self._get_explorer_link(tx_hash.hex())
            return f"⛓️ Transfer transaction sent: {tx_link}"

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            raise

    def _get_swap_route(self, token_in: str, token_out: str, amount_in: float) -> Dict[str, Any]:
        """Get the best swap route from Kyberswap API"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            # Convert amount to raw value
            if token_in.lower() == self.NATIVE_TOKEN.lower():
                amount_raw = Wei(web3.to_wei(amount_in, 'ether'))
            else:
                token_contract = web3.eth.contract(
                    address=Web3.to_checksum_address(token_in),
                    abi=self.ERC20_ABI
                )
                decimals = token_contract.functions.decimals().call()
                amount_raw = Wei(int(amount_in * (10 ** decimals)))
            
            # Set up API request
            url = f"{self.aggregator_api}/routes"
            headers = {"x-client-id": "ZerePyBot"}
            params = {
                "tokenIn": token_in,
                "tokenOut": token_out,
                "amountIn": str(amount_raw),
                "gasInclude": "true"
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise SonicConnectionError(f"API error: {data.get('message')}")
                
            result = data.get("data")
            if not isinstance(result, dict):
                raise SonicConnectionError("Invalid route data returned from API")
            return result
                
        except Exception as e:
            logger.error(f"Failed to get swap route: {e}")
            raise

    def _get_encoded_swap_data(self, route_summary: Dict[str, Any], slippage: float = 0.5) -> str:
        """Get encoded swap data from Kyberswap API"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            private_key = os.getenv('SONIC_PRIVATE_KEY')
            if not private_key:
                raise SonicConnectionError("No wallet configured")

            account = web3.eth.account.from_key(private_key)
            
            url = f"{self.aggregator_api}/route/build"
            headers = {"x-client-id": "zerepy"}
            
            payload = {
                "routeSummary": route_summary,
                "sender": account.address,
                "recipient": account.address,
                "slippageTolerance": int(slippage * 100),  # Convert to bps
                "deadline": int(time.time() + 1200),  # 20 minutes
                "source": "ZerePyBot"
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise SonicConnectionError(f"API error: {data.get('message')}")
                
            encoded_data = data.get("data", {}).get("data")
            if not isinstance(encoded_data, str):
                raise SonicConnectionError("Invalid encoded data returned from API")
            return encoded_data
                
        except Exception as e:
            logger.error(f"Failed to encode swap data: {e}")
            raise
    
    def _handle_token_approval(self, token_address: str, spender_address: str, amount: Wei) -> None:
        """Handle token approval for spender"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            private_key = os.getenv('SONIC_PRIVATE_KEY')
            if not private_key:
                raise SonicConnectionError("No wallet configured")

            account = web3.eth.account.from_key(private_key)
            
            token_contract = web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            
            # Check current allowance
            current_allowance = token_contract.functions.allowance(
                account.address,
                spender_address
            ).call()
            
            if current_allowance < amount:
                approve_tx: TxParams = {
                    'from': account.address,
                    'nonce': web3.eth.get_transaction_count(account.address),
                    'gasPrice': web3.eth.gas_price,
                    'chainId': web3.eth.chain_id
                }
                
                approve_tx = token_contract.functions.approve(
                    spender_address,
                    amount
                ).build_transaction(approve_tx)
                
                signed_approve = account.sign_transaction(approve_tx)
                tx_hash = web3.eth.send_raw_transaction(signed_approve.rawTransaction)
                logger.info(f"Approval transaction sent: {self._get_explorer_link(tx_hash.hex())}")
                
                # Wait for approval to be mined
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                if not receipt or receipt.get('status') != 1:
                    raise SonicConnectionError("Approval transaction failed")
                
        except Exception as e:
            logger.error(f"Approval failed: {e}")
            raise

    def swap(self, token_in: str, token_out: str, amount: float, slippage: float = 0.5) -> str:
        """Execute a token swap using the KyberSwap router"""
        try:
            web3 = self._get_web3(verbose=True)
            if not web3:
                raise SonicConnectionError("Web3 not initialized")

            private_key = os.getenv('SONIC_PRIVATE_KEY')
            if not private_key:
                raise SonicConnectionError("No wallet configured")

            account = web3.eth.account.from_key(private_key)

            # Check token balance before proceeding
            current_balance = self.get_balance(
                address=account.address,
                token_address=None if token_in.lower() == self.NATIVE_TOKEN.lower() else token_in
            )
            
            if current_balance < amount:
                raise ValueError(f"Insufficient balance. Required: {amount}, Available: {current_balance}")
                
            # Get optimal swap route
            route_data = self._get_swap_route(token_in, token_out, amount)
            
            # Get encoded swap data
            encoded_data = self._get_encoded_swap_data(route_data["routeSummary"], slippage)
            
            # Get router address from route data
            router_address = route_data.get("routerAddress")
            if not router_address:
                raise SonicConnectionError("No router address in route data")
            
            # Handle token approval if not using native token
            if token_in.lower() != self.NATIVE_TOKEN.lower():
                if token_in.lower() == "0x039e2fb66102314ce7b64ce5ce3e5183bc94ad38".lower():  # $S token
                    amount_raw = Wei(web3.to_wei(amount, 'ether'))
                else:
                    token_contract = web3.eth.contract(
                        address=Web3.to_checksum_address(token_in),
                        abi=self.ERC20_ABI
                    )
                    decimals = token_contract.functions.decimals().call()
                    raw_amount = int(amount * (10 ** decimals))
                    amount_raw = Wei(raw_amount)
                self._handle_token_approval(token_in, router_address, amount_raw)
            
            # Prepare transaction
            base_tx: TxParams = {
                'from': account.address,
                'to': Web3.to_checksum_address(router_address),
                'data': HexBytes(encoded_data) if isinstance(encoded_data, str) else encoded_data,
                'nonce': web3.eth.get_transaction_count(account.address),
                'gasPrice': web3.eth.gas_price,
                'chainId': web3.eth.chain_id,
                'value': Wei(web3.to_wei(amount, 'ether')) if token_in.lower() == self.NATIVE_TOKEN.lower() else Wei(0)
            }
            
            # Estimate gas
            try:
                base_tx['gas'] = web3.eth.estimate_gas(base_tx)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default gas limit")
                base_tx['gas'] = 500000  # Default gas limit
            
            # Sign and send transaction
            signed_tx = account.sign_transaction(base_tx)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt and check status
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            if not receipt or receipt.get('status') != 1:
                raise SonicConnectionError("Swap transaction failed")
            
            # Return explorer link
            tx_link = self._get_explorer_link(tx_hash.hex())
            return f"🔄 Swap transaction sent: {tx_link}"
                
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            raise
    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute a Sonic action"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        load_dotenv()
        
        if not self.is_configured(verbose=True):
            raise SonicConnectionError("Sonic is not properly configured")

        method = self.actions[action_name]
        return method(**kwargs)
