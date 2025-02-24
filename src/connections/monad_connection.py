import logging
import os
import time
import requests
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv, set_key
from web3 import Web3
from web3.middleware import geth_poa_middleware
from src.constants.networks import EVM_NETWORKS
from src.constants.abi import ERC20_ABI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.monad_connection")

# Constants specific to Monad testnet
MONAD_BASE_GAS_PRICE = 50  # gwei - hardcoded for testnet
MONAD_CHAIN_ID = 10143
MONAD_SCANNER_URL = "testnet.monadexplorer.com"
ZERO_EX_API_URL = "https://api.0x.org/swap"

class MonadConnectionError(Exception):
    """Base exception for Monad connection errors"""
    pass

class MonadConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Monad connection...")
        self._web3 = None
        self.NATIVE_TOKEN = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        
        # Get network configuration
        self.rpc_url = config.get("rpc")
        if not self.rpc_url:
            raise ValueError("RPC URL must be provided in config")
            
        self.scanner_url = MONAD_SCANNER_URL
        self.chain_id = MONAD_CHAIN_ID
        
        super().__init__(config)
        self._initialize_web3()

    def _get_explorer_link(self, tx_hash: str) -> str:
        """Generate block explorer link for transaction"""
        return f"https://{self.scanner_url}/tx/{tx_hash}"

    def _initialize_web3(self) -> None:
        """Initialize Web3 connection with retry logic"""
        if not self._web3:
            for attempt in range(3):
                try:
                    self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                    self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    
                    if not self._web3.is_connected():
                        raise MonadConnectionError("Failed to connect to Monad network")
                    
                    chain_id = self._web3.eth.chain_id
                    if chain_id != self.chain_id:
                        raise MonadConnectionError(f"Connected to wrong chain. Expected {self.chain_id}, got {chain_id}")
                        
                    logger.info(f"Connected to Monad network with chain ID: {chain_id}")
                    break
                    
                except Exception as e:
                    if attempt == 2:
                        raise MonadConnectionError(f"Failed to initialize Web3 after 3 attempts: {str(e)}")
                    logger.warning(f"Web3 initialization attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(1)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Monad configuration from JSON"""
        if "rpc" not in config:
            raise ValueError("RPC URL must be provided in config")
        return config

    def register_actions(self) -> None:
        """Register available Monad actions"""
        self.actions = {
            "get-balance": Action(
                name="get-balance",
                parameters=[
                    ActionParameter("token_address", False, str, "Token address (optional, native token if not provided)")
                ],
                description="Get native or token balance"
            ),
            "transfer": Action(
                name="transfer", 
                parameters=[
                    ActionParameter("to_address", True, str, "Recipient address"),
                    ActionParameter("amount", True, float, "Amount to transfer"),
                    ActionParameter("token_address", False, str, "Token address (optional, native token if not provided)")
                ],
                description="Send native token or tokens"
            ),
            "get-address": Action(
                name="get-address",
                parameters=[],
                description="Get your Monad wallet address"
            ),
            "swap": Action(
                name="swap",
                parameters=[
                    ActionParameter("token_in", True, str, "Input token address"),
                    ActionParameter("token_out", True, str, "Output token address"),
                    ActionParameter("amount", True, float, "Amount to swap"),
                    ActionParameter("slippage", False, float, "Max slippage percentage (default 0.5%)")
                ],
                description="Swap tokens using 0x API"
            )
        }

    def _get_current_account(self) -> 'LocalAccount':
        """Get current account from private key"""
        private_key = os.getenv('MONAD_PRIVATE_KEY')
        if not private_key:
            raise MonadConnectionError("No wallet private key configured")
        return self._web3.eth.account.from_key(private_key)

    def configure(self) -> bool:
        """Sets up Monad wallet"""
        logger.info("\n⛓️ MONAD SETUP")
        
        if self.is_configured():
            logger.info("Monad connection is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            # Get wallet private key  
            private_key = input("\nEnter your wallet private key: ")
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
                
            # Validate private key format
            if len(private_key) != 66 or not all(c in '0123456789abcdefABCDEF' for c in private_key[2:]):
                raise ValueError("Invalid private key format")
            
            # Test private key by deriving address
            account = self._web3.eth.account.from_key(private_key)
            logger.info(f"\nDerived address: {account.address}")

            # Test connection
            if not self._web3.is_connected():
                raise MonadConnectionError("Failed to connect to Monad network")
            
            # Save credentials
            set_key('.env', 'MONAD_PRIVATE_KEY', private_key)

            # Get optional 0x API key
            zeroex_key = input("\nEnter your 0x API key (optional, press Enter to skip): ")
            if zeroex_key.strip():
                set_key('.env', 'ZEROEX_API_KEY', zeroex_key)

            logger.info("\n✅ Monad configuration saved successfully!")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {str(e)}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Monad connection is properly configured"""
        try:
            load_dotenv()
            
            if not os.getenv('MONAD_PRIVATE_KEY'):
                if verbose:
                    logger.error("Missing MONAD_PRIVATE_KEY in .env")
                return False

            if not self._web3.is_connected():
                if verbose:
                    logger.error("Not connected to Monad network")
                return False
                
            # Test account access
            account = self._get_current_account()
            balance = self._web3.eth.get_balance(account.address)
                
            return True

        except Exception as e:
            if verbose:
                logger.error(f"Configuration check failed: {e}")
            return False

    def get_address(self) -> str:
        """Get the wallet address"""
        try:
            account = self._get_current_account()
            return f"Your Monad address: {account.address}"
        except Exception as e:
            return f"Failed to get address: {str(e)}"

    def get_balance(self, token_address: Optional[str] = None) -> float:
        """Get native or token balance for the configured wallet"""
        try:
            account = self._get_current_account()
            
            if token_address is None or token_address.lower() == self.NATIVE_TOKEN.lower():
                raw_balance = self._web3.eth.get_balance(account.address)
                return self._web3.from_wei(raw_balance, 'ether')
            
            contract = self._web3.eth.contract(
                address=Web3.to_checksum_address(token_address), 
                abi=ERC20_ABI 
            )
            decimals = contract.functions.decimals().call()
            raw_balance = contract.functions.balanceOf(account.address).call()
            return raw_balance / (10 ** decimals)
            
        except Exception as e:
            logger.error(f"Failed to get balance: {str(e)}")
            return 0

    def _prepare_transfer_tx(
        self, 
        to_address: str,
        amount: float,
        token_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Prepare transfer transaction with Monad-specific gas handling"""
        try:
            account = self._get_current_account()
            
            # Get latest nonce
            nonce = self._web3.eth.get_transaction_count(account.address)
            
            # Use fixed gas price for testnet
            gas_price = Web3.to_wei(MONAD_BASE_GAS_PRICE, 'gwei')
            
            if token_address and token_address.lower() != self.NATIVE_TOKEN.lower():
                # Prepare ERC20 transfer
                contract = self._web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                decimals = contract.functions.decimals().call()
                amount_raw = int(amount * (10 ** decimals))
                
                # Monad charges based on gas limit, not usage
                tx = contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    amount_raw
                ).build_transaction({
                    'from': account.address,
                    'nonce': nonce,
                    'gasPrice': gas_price,
                    'chainId': self.chain_id
                })
            else:
                # Prepare native token transfer
                tx = {
                    'nonce': nonce,
                    'to': Web3.to_checksum_address(to_address),
                    'value': self._web3.to_wei(amount, 'ether'),
                    'gas': 21000,  # Standard ETH transfer gas
                    'gasPrice': gas_price,
                    'chainId': self.chain_id
                }
            
            return tx

        except Exception as e:
            logger.error(f"Failed to prepare transaction: {str(e)}")
            raise

    def transfer(
        self,
        to_address: str,
        amount: float,
        token_address: Optional[str] = None
    ) -> str:
        """Transfer tokens with Monad-specific balance validation"""
        try:
            account = self._get_current_account()

            # Check balance including gas cost since Monad charges on gas limit
            gas_cost = Web3.to_wei(MONAD_BASE_GAS_PRICE * 21000, 'gwei')
            gas_cost_eth = float(self._web3.from_wei(gas_cost, 'ether'))
            total_required = float(amount) + gas_cost_eth
            
            current_balance = float(self.get_balance(token_address=token_address))
            if current_balance < total_required:
                raise ValueError(
                    f"Insufficient balance. Required: {total_required}, Available: {current_balance}"
                )

            # Prepare and send transaction
            tx = self._prepare_transfer_tx(to_address, amount, token_address)
            signed = account.sign_transaction(tx)
            tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
            
            tx_url = self._get_explorer_link(tx_hash.hex())
            return f"Transaction sent: {tx_url}"

        except Exception as e:
            logger.error(f"Transfer failed: {str(e)}")
            raise

    def _get_swap_quote(self, token_in: str, token_out: str, amount: float, sender: str) -> Dict:
        """Get swap quote from 0x API using v2 endpoints"""
        try:
            load_dotenv()
            
            # Use 0x API's native token identifier for ETH
            if token_in == "0x0000000000000000000000000000000000000000" or token_in.lower() == self.NATIVE_TOKEN.lower():
                amount_raw = self._web3.to_wei(amount, 'ether')
                token_in = self.NATIVE_TOKEN
                logger.debug(f"Using native token identifier: {token_in}")
            else:
                token_contract = self._web3.eth.contract(
                    address=Web3.to_checksum_address(token_in),
                    abi=ERC20_ABI
                )
                decimals = token_contract.functions.decimals().call()
                amount_raw = int(amount * (10 ** decimals))

            # Set up API request according to v2 spec
            headers = {
                "0x-api-key": os.getenv('ZEROEX_API_KEY'),
                "0x-version": "v2"
            }
            
            params = {
                "sellToken": token_in,
                "buyToken": token_out,
                "sellAmount": str(amount_raw),
                "chainId": str(self.chain_id),
                "taker": sender
            }

            url = f"{ZERO_EX_API_URL}/permit2/quote"
            logger.debug("\nHEADERS ")
            logger.debug(headers)
            logger.debug("\nPARAMS ")
            logger.debug(params)
            logger.debug("\nURL ")
            logger.debug(url)
            response = requests.get(
                url,
                headers=headers,
                params=params
            )
            logger.debug(f"\nHEADER FROM OBJECT : {response.request.headers}")
            response.raise_for_status()

                # Log full response details
            logger.info("\n=== 0x API Response ===")
            logger.info(f"Status Code: {response.status_code}")
            logger.info("Headers:")
            for key, value in response.headers.items():
                logger.info(f"{key}: {value}")
            logger.info("\nResponse Body:")
            logger.info(response.text)
            logger.info("=== End Response ===\n")
            
            data = response.json()
            return data

        except Exception as e:
            logger.error(f"Failed to get swap quote: {str(e)}")
            raise

    def swap(self, token_in: str, token_out: str, amount: float, slippage: float = 0.5) -> str:
        """Execute token swap using 0x API with Monad-specific handling"""
        try:
            logger.debug(f"\nStarting swap with parameters:")
            logger.debug(f"token_in: {token_in}")
            logger.debug(f"token_out: {token_out}")
            logger.debug(f"amount: {amount}")
            
            account = self._get_current_account()
            logger.debug(f"Account address: {account.address}")

            # For native token swaps, use None as token_address for balance check
            is_native = (token_in.lower() == self.NATIVE_TOKEN.lower() or 
                        token_in == "0x0000000000000000000000000000000000000000")
            
            current_balance = self.get_balance(token_address=None if is_native else token_in)
            logger.debug(f"Current balance: {current_balance}")
            
            if current_balance < amount:
                raise ValueError(f"Insufficient balance. Required: {amount}, Available: {current_balance}")
            
            # Get swap quote with v2 API
            quote_data = self._get_swap_quote(
                token_in,
                token_out,
                amount,
                account.address
            )
            
            logger.debug(f"Quote data received: {quote_data}")

            # Extract transaction data from quote
            transaction = quote_data.get("transaction")
            if not transaction or not transaction.get("to") or not transaction.get("data"):
                raise ValueError("Invalid transaction data in quote")
                
            # Handle token approval if needed for non-native tokens
            if not is_native:
                spender_address = quote_data.get("allowanceTarget")
                amount_raw = int(quote_data.get("sellAmount"))
                    
                if spender_address:  # Only attempt approval if we have a spender address
                    approval_hash = self._handle_token_approval(token_in, spender_address, amount_raw)
                    if approval_hash:
                        logger.info(f"Token approval transaction: {self._get_explorer_link(approval_hash)}")
                        # Wait for approval confirmation
                        self._web3.eth.wait_for_transaction_receipt(approval_hash)
            
            # Prepare swap transaction using quote data
            tx = {
                'from': account.address,
                'to': Web3.to_checksum_address(transaction["to"]),
                'data': transaction["data"],
                'value': self._web3.to_wei(amount, 'ether') if is_native else 0,
                'nonce': self._web3.eth.get_transaction_count(account.address),
                'gasPrice': Web3.to_wei(MONAD_BASE_GAS_PRICE, 'gwei'),
                'chainId': self.chain_id,
            }

            # Estimate gas or use quote's gas estimate
            try:
                tx['gas'] = int(transaction.get("gas", 0)) or self._web3.eth.estimate_gas(tx)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default gas limit")
                tx['gas'] = 500000  # Default gas limit for swaps

            # Sign and send transaction
            signed_tx = account.sign_transaction(tx)
            tx_hash = self._web3.eth.send_raw_transaction(signed_tx.rawTransaction)

            tx_url = self._get_explorer_link(tx_hash.hex())
            return f"Swap transaction sent: {tx_url}"
                
        except Exception as e:
            logger.error(f"Swap failed: {str(e)}")
            raise

        def _handle_token_approval(
            self,
            token_address: str,
            spender_address: str,
            amount: int
        ) -> Optional[str]:
            """Handle token approval for spender, returns tx hash if approval needed"""
            try:
                account = self._get_current_account()
                
                token_contract = self._web3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                
                # Check current allowance
                current_allowance = token_contract.functions.allowance(
                    account.address,
                    spender_address
                ).call()
                
                if current_allowance < amount:
                    # Prepare approval transaction with fixed gas price
                    approve_tx = token_contract.functions.approve(
                        spender_address,
                        amount
                    ).build_transaction({
                        'from': account.address,
                        'nonce': self._web3.eth.get_transaction_count(account.address),
                        'gasPrice': Web3.to_wei(MONAD_BASE_GAS_PRICE, 'gwei'),
                        'chainId': self.chain_id
                    })
                    
                    # Set fixed gas for approval on Monad
                    approve_tx['gas'] = 100000  # Standard approval gas
                    
                    # Sign and send approval transaction
                    signed_approve = account.sign_transaction(approve_tx)
                    tx_hash = self._web3.eth.send_raw_transaction(signed_approve.rawTransaction)
                    
                    # Wait for approval to be mined
                    receipt = self._web3.eth.wait_for_transaction_receipt(tx_hash)
                    if receipt['status'] != 1:
                        raise ValueError("Token approval failed")
                    
                    return tx_hash.hex()
                    
                return None

            except Exception as e:
                logger.error(f"Token approval failed: {str(e)}")
                raise

    def perform_action(self, action_name: str, kwargs: Dict[str, Any]) -> Any:
        """Execute a Monad action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        load_dotenv()
        
        if not self.is_configured(verbose=True):
            raise MonadConnectionError("Monad connection is not properly configured")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        
        try:
            return method(**kwargs)
        except Exception as e:
            logger.error(f"Action {action_name} failed: {str(e)}")
            raise