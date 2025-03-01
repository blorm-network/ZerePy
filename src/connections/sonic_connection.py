import logging
import os
import json
import time
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv, set_key
from web3 import Web3
from web3.middleware import geth_poa_middleware
from src.constants.abi import ERC20_ABI
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.constants.networks import SONIC_NETWORKS

# Configure logging
logger = logging.getLogger("connections.sonic_connection")
file_handler = logging.FileHandler("sonic_connection.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
logger.addHandler(file_handler)

# Contract addresses
BERRY_TEMP_AGENT_ADDRESS = "0xF28eC6250Fc5101D814dd78F9b1673b5e3a55cFa"
BERRY_MANAGER_ADDRESS = "0x56516C11f350EeCe25AeA9e36ECd36CB6c71030d"

# Transaction history storage
transaction_history = []
MAX_TRANSACTION_HISTORY = 100

class SonicConnectionError(Exception):
    """Base exception for Sonic connection errors"""
    pass

class SonicConnection(BaseConnection):
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Sonic connection...")
        self._web3 = None
        self.account = None
        self.contract_abis = {}
        self.contract_instances = {}
        self.transaction_stats = {
            "sent": 0,
            "successful": 0,
            "failed": 0,
            "total_gas_used": 0,
            "avg_gas_used": 0,
            "last_tx_time": None,
            "total_cost": 0
        }
        
        # Enable mock mode if specified
        self.use_mock_mode = config.get("use_mock_mode", False)
        if self.use_mock_mode:
            logger.info("📌 Running in MOCK MODE - No real blockchain transactions will be made")
        
        # Get network configuration
        network = config.get("network", "testnet")
        if network not in SONIC_NETWORKS:
            raise ValueError(f"Invalid network '{network}'. Must be one of: {', '.join(SONIC_NETWORKS.keys())}")
            
        network_config = SONIC_NETWORKS[network]
        self.explorer = network_config["scanner_url"]
        self.rpc_url = network_config["rpc_url"]
        self.network_name = network
        
        # Connection retry parameters
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 2)
        self.exponential_backoff = config.get("exponential_backoff", True)
        
        # Initialize with base config
        super().__init__(config)
        
        # Initialize mock data if in mock mode
        if self.use_mock_mode:
            self.mock_data = self._load_default_mock_data()
            logger.info("Loaded default mock data for mock mode")
        
        # Initialize web3, contracts, and account
        self._initialize_web3()
        self.ERC20_ABI = ERC20_ABI
        self.NATIVE_TOKEN = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        
        try:
            self._load_contract_abis()
            self._initialize_contracts()
            self._load_account()
            logger.info("Sonic connection initialization complete")
        except Exception as e:
            logger.error(f"Error during connection initialization: {e}", exc_info=True)
            if not self.use_mock_mode:
                raise

    def _get_explorer_link(self, tx_hash: str) -> str:
        """Generate block explorer link for transaction"""
        return f"{self.explorer}/tx/{tx_hash}"

    def _initialize_web3(self):
        """Initialize Web3 connection with retry logic"""
        if not self._web3:
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                    self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    
                    if not self._web3.is_connected() and not self.use_mock_mode:
                        raise SonicConnectionError(f"Failed to connect to Sonic network: {self.network_name}")
                    
                    chain_id = self._web3.eth.chain_id
                    logger.info(f"Connected to network with chain ID: {chain_id}")
                    
                    # Connection successful, exit retry loop
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count >= self.max_retries and not self.use_mock_mode:
                        logger.error(f"Failed to initialize Web3 after {self.max_retries} attempts: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff if enabled
                    delay = self.retry_delay
                    if self.exponential_backoff:
                        delay = self.retry_delay * (2 ** (retry_count - 1))
                    
                    logger.warning(f"Web3 initialization attempt {retry_count} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    
    def _load_default_mock_data(self):
        """Create default mock data when in mock mode"""
        return {
            "batches": [
                {
                    "batchId": 0,
                    "berryType": "Strawberry",
                    "startTime": int((datetime.now() - timedelta(hours=24)).timestamp()),
                    "endTime": 0,
                    "isActive": True,
                    "status": 1,  # 1 = InTransit
                    "qualityScore": 85,
                    "predictedShelfLife": 60 * 60 * 60  # 60 hours in seconds
                },
                {
                    "batchId": 1,
                    "berryType": "Blueberry",
                    "startTime": int((datetime.now() - timedelta(hours=18)).timestamp()),
                    "endTime": 0,
                    "isActive": True,
                    "status": 1,
                    "qualityScore": 90,
                    "predictedShelfLife": 72 * 60 * 60
                }
            ],
            "temperature_history": [
                # Batch 0 temperature readings (some with breaches)
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=24)).timestamp()), "temperature": 20, "location": "Cold Storage"},
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=20)).timestamp()), "temperature": 25, "location": "Loading Dock"},
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=16)).timestamp()), "temperature": 28, "location": "Transport"},
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=12)).timestamp()), "temperature": 45, "location": "Transport"},
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=8)).timestamp()), "temperature": 32, "location": "Transport"},
                {"batchId": 0, "timestamp": int((datetime.now() - timedelta(hours=4)).timestamp()), "temperature": 22, "location": "Delivery"},
                
                # Batch 1 temperature readings (mostly good)
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=18)).timestamp()), "temperature": 22, "location": "Cold Storage"},
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=15)).timestamp()), "temperature": 24, "location": "Loading Dock"},
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=12)).timestamp()), "temperature": 26, "location": "Transport"},
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=9)).timestamp()), "temperature": 30, "location": "Transport"},
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=6)).timestamp()), "temperature": 28, "location": "Transport"},
                {"batchId": 1, "timestamp": int((datetime.now() - timedelta(hours=3)).timestamp()), "temperature": 23, "location": "Delivery"}
            ],
            "supplier_details": {
                "account": "0x1e43eeB0307bb3466Cd237fE58570E6A3996d8ff",
                "isRegistered": True,
                "reputation": 85,
                "totalBatches": 12,
                "successfulBatches": 10,
                "lastActionTime": int(datetime.now().timestamp()) - 3600
            },
            "batch_count": 2
        }
    
    
    def _load_account(self):
        """Load account from private key with better error handling"""
        try:
            load_dotenv()
            private_key = os.getenv('SONIC_PRIVATE_KEY')
            if not private_key:
                logger.warning("No private key found in environment variables")
                return
                
            # Check if the private key format is valid
            if not private_key.startswith('0x') or len(private_key) != 66:  # 0x + 64 hex chars
                logger.warning("Private key format appears invalid. Expected 0x followed by 64 hex characters.")
                if not private_key.startswith('0x'):
                    # Try to add 0x prefix if missing
                    private_key = '0x' + private_key
                    logger.info("Added '0x' prefix to private key")
            
            try:
                self.account = self._web3.eth.account.from_key(private_key)
                logger.info(f"Account loaded with address: {self.account.address}")
                
                # Log account balance for debugging
                if not self.use_mock_mode:
                    try:
                        balance = self._web3.eth.get_balance(self.account.address)
                        balance_eth = self._web3.from_wei(balance, 'ether')
                        logger.info(f"Account balance: {balance_eth} Sonic Tokens")
                        
                        # Warn if balance is low
                        if balance_eth < 1:
                            logger.warning(f"⚠️ Account balance is low: {balance_eth} Sonic Tokens. This may affect transaction processing.")
                    except Exception as e:
                        logger.warning(f"Could not get account balance: {e}")
            except Exception as e:
                logger.error(f"Error loading account from private key: {e}")
                raise
                
        except Exception as e:
            logger.warning(f"Could not load account: {e}")
    
    def _load_contract_abis(self):
        """Load contract ABIs from artifact files with enhanced error handling"""
        try:
            # Get the project root directory
            project_root = os.getcwd()
            
            # List of contracts to load
            contracts_to_load = [
                {
                    "name": "BerryTempAgent",
                    "path": os.path.join(project_root, "artifacts", "contracts", "core", "BerryTempAgent.json"),
                    "address": BERRY_TEMP_AGENT_ADDRESS
                },
                {
                    "name": "BerryManager",
                    "path": os.path.join(project_root, "artifacts", "contracts", "core", "BerryManager.json"),
                    "address": BERRY_MANAGER_ADDRESS
                }
            ]
            
            # Load each contract ABI
            for contract in contracts_to_load:
                try:
                    if not os.path.exists(contract["path"]):
                        logger.warning(f"Contract artifact not found: {contract['path']}")
                        continue
                        
                    with open(contract["path"], 'r') as f:
                        contract_json = json.load(f)
                        
                    if "abi" not in contract_json:
                        logger.warning(f"No ABI found in contract artifact: {contract['name']}")
                        continue
                        
                    self.contract_abis[contract["name"]] = contract_json["abi"]
                    logger.info(f"Loaded ABI for {contract['name']}")
                except Exception as e:
                    logger.error(f"Failed to load ABI for {contract['name']}: {e}")
            
            # Set named ABI variables for backward compatibility
            self.BERRY_TEMP_AGENT_ABI = self.contract_abis.get("BerryTempAgent", [])
            self.BERRY_MANAGER_ABI = self.contract_abis.get("BerryManager", [])
            
            logger.info(f"Successfully loaded contract ABIs: {', '.join(self.contract_abis.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to load contract ABIs: {e}", exc_info=True)
            # Fallback to empty ABIs
            self.BERRY_TEMP_AGENT_ABI = []
            self.BERRY_MANAGER_ABI = []
    
    def _initialize_contracts(self):
        """Initialize contract instances with better error handling"""
        try:
            contracts_to_initialize = [
                {"name": "berry_temp_agent", "address": BERRY_TEMP_AGENT_ADDRESS, "abi": self.BERRY_TEMP_AGENT_ABI},
                {"name": "berry_manager", "address": BERRY_MANAGER_ADDRESS, "abi": self.BERRY_MANAGER_ABI}
            ]
            
            initialized_contracts = []
            
            for contract in contracts_to_initialize:
                try:
                    if not contract["abi"]:
                        logger.warning(f"Empty ABI for {contract['name']}, skipping initialization")
                        continue
                        
                    contract_instance = self._web3.eth.contract(
                        address=Web3.to_checksum_address(contract["address"]),
                        abi=contract["abi"]
                    )
                    
                    # Store contract instance in both dict and as attribute for compatibility
                    self.contract_instances[contract["name"]] = contract_instance
                    setattr(self, contract["name"], contract_instance)
                    
                    initialized_contracts.append(contract["name"])
                except Exception as e:
                    logger.error(f"Failed to initialize contract {contract['name']}: {e}")
                    if not self.use_mock_mode:
                        raise
            
            if initialized_contracts:
                logger.info(f"Successfully initialized contract instances: {', '.join(initialized_contracts)}")
            else:
                logger.warning("No contracts were successfully initialized")
            
        except Exception as e:
            if not self.use_mock_mode:
                logger.error(f"Failed to initialize contract instances: {e}", exc_info=True)
                raise
            else:
                logger.warning(f"Contract initialization error (in mock mode): {e}")
                
            self.berry_temp_agent = None
            self.berry_manager = None

    def get_optimal_gas_price(self):
        """Get optimal gas price for Sonic Blaze Testnet with improved reliability"""
        try:
            # Set a minimum gas price high enough to avoid "underpriced" errors
            # For Sonic Blaze Testnet, 10 gwei seems to be the minimum
            minimum_gas_price = self._web3.to_wei(10, 'gwei')
            
            # Get current network gas price
            network_gas_price = self._web3.eth.gas_price
            
            # Use the higher of the two values
            optimal_price = max(minimum_gas_price, network_gas_price * 2)
            
            # Cap the gas price at a reasonable maximum (50 gwei)
            max_gas_price = self._web3.to_wei(50, 'gwei')
            if optimal_price > max_gas_price:
                logger.warning(f"Gas price capped at 50 gwei (was {self._web3.from_wei(optimal_price, 'gwei')} gwei)")
                optimal_price = max_gas_price
                
            logger.info(f"Using gas price: {self._web3.from_wei(optimal_price, 'gwei')} gwei")
            return optimal_price
        except Exception as e:
            logger.warning(f"Error determining optimal gas price: {e}, using default 10 gwei")
            return self._web3.to_wei(10, 'gwei')
        
    def _safe_gas_estimation(self, tx_params, contract_func, args):
        """Safely estimate gas without panicking on errors"""
        try:
           tx_for_estimate = contract_func(*args).build_transaction(tx_params)
           estimated_gas = self._web3.eth.estimate_gas(tx_for_estimate)
           return int(estimated_gas * 1.2)  # 20% buffer
        except Exception as e:
           logger.warning(f"Gas estimation failed: {e}, using safe default")
           # Use higher default for processAgentRecommendation which is failing
           if hasattr(contract_func, "__name__") and contract_func.__name__ == "processAgentRecommendation":
               return 500000
           return 300000  # Safe default for other functions
    
    

    def _estimate_transaction_gas(self, tx_params, contract_func, args):
        """Estimate gas for a transaction and check if enough balance is available with better error handling"""
        try:
            # Create transaction object for estimation
            tx_for_estimate = contract_func(*args).build_transaction(tx_params)
            
            # Estimate gas with a 20% buffer
            estimated_gas = 0
            
            try:
                base_estimate = self._web3.eth.estimate_gas(tx_for_estimate)
                estimated_gas = int(base_estimate * 1.2)  # 20% buffer
                logger.debug(f"Base gas estimate: {base_estimate}, with buffer: {estimated_gas}")
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using safe default")
                # Use a safe default based on transaction type
                method_name = contract_func.__name__ if hasattr(contract_func, "__name__") else "unknown"
                
                # Set default gas limits based on method
                if "create" in method_name.lower():
                    estimated_gas = 200000
                elif "process" in method_name.lower():
                    estimated_gas = 300000
                elif "complete" in method_name.lower():
                    estimated_gas = 400000
                else:
                    estimated_gas = 500000  # Higher default for unknown methods
                
                logger.info(f"Using default gas limit for {method_name}: {estimated_gas}")
            
            # Get optimal gas price
            gas_price = self.get_optimal_gas_price()
            
            # Calculate total cost
            total_cost = estimated_gas * gas_price
            
            # Get account balance
            balance = 0
            if self.account:
                try:
                    balance = self._web3.eth.get_balance(self.account.address)
                except Exception as e:
                    logger.warning(f"Failed to get account balance: {e}")
            
            # Log for debugging
            logger.info(f"Estimated gas: {estimated_gas}")
            logger.info(f"Gas price: {self._web3.from_wei(gas_price, 'gwei')} gwei")
            logger.info(f"Total cost: {self._web3.from_wei(total_cost, 'ether')} Sonic Tokens")
            if balance > 0:
                logger.info(f"Account balance: {self._web3.from_wei(balance, 'ether')} Sonic Tokens")
            
            return {
                "has_funds": balance >= total_cost,
                "gas_limit": estimated_gas,
                "gas_price": gas_price,
                "total_cost": total_cost,
                "balance": balance
            }
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}", exc_info=True)
            # Return conservative defaults
            return {
                "has_funds": True,  # Assume funds are available if estimation fails
                "gas_limit": 500000,  # Higher default gas limit for safety
                "gas_price": self.get_optimal_gas_price(),
                "total_cost": 0,
                "balance": 0
            }

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Sonic configuration from JSON"""
        required = ["network"]
        missing = [field for field in required if field not in config]
        if missing:
            raise ValueError(f"Missing config fields: {', '.join(missing)}")
        
        if config["network"] not in SONIC_NETWORKS:
            raise ValueError(f"Invalid network '{config['network']}'. Must be one of: {', '.join(SONIC_NETWORKS.keys())}")
            
        return config

    def register_actions(self) -> None:
        """Register available actions for the agent"""
        self.actions = {
            # Berry Temperature Monitoring Actions
            "monitor-berry-temperature": Action(
                name="monitor-berry-temperature",
                parameters=[
                    ActionParameter("batch_id", False, int, "Batch ID to monitor"),
                    ActionParameter("temperature", False, float, "Temperature reading"),
                    ActionParameter("location", False, str, "Current location")
                ],
                description="Monitor and analyze temperature data for berry shipments"
            ),
            "manage-berry-quality": Action(
                name="manage-berry-quality",
                parameters=[
                    ActionParameter("batch_id", False, int, "Batch ID to assess")
                ],
                description="Assess and predict berry quality based on temperature history"
            ),
            "process-agent-recommendations": Action(
                name="process-agent-recommendations",
                parameters=[
                    ActionParameter("batch_id", True, int, "Batch ID to process"),
                ],
                description="Process agent recommendations and update supplier reputation"
            ),
            "manage-batch-lifecycle": Action(
                name="manage-batch-lifecycle",
                parameters=[
                    ActionParameter("action", True, str, "Action to perform (create, complete, status, report)"),
                    ActionParameter("batch_id", False, int, "Batch ID for existing batches"),
                    ActionParameter("berry_type", False, str, "Berry type for new batches")
                ],
                description="Manage berry batch lifecycle from creation to delivery"
            ),
            "system-health-check": Action(
                name="system-health-check",
                parameters=[
                    ActionParameter("reset_counters", False, bool, "Reset health metrics counters")
                ],
                description="Perform a system health check and return metrics"
            ),
            "manage-batch-sequence": Action(
                name="manage-batch-sequence",
                parameters=[
                    ActionParameter("berry_type", False, str, "Berry type for the batch"),
                    ActionParameter("temperatures", False, list, "List of temperature readings"),
                    ActionParameter("locations", False, list, "List of locations"),
                    ActionParameter("complete_shipment", False, bool, "Whether to complete the shipment")
                ],
                description="Execute a complete batch lifecycle sequence"
            ),
            
            # Original Sonic Actions
            "get-token-by-ticker": Action(
                name="get-token-by-ticker",
                parameters=[
                    ActionParameter("ticker", True, str, "Token ticker symbol to look up")
                ],
                description="Get token address by ticker symbol"
            ),
            "get-balance": Action(
                name="get-balance",
                parameters=[
                    ActionParameter("address", False, str, "Address to check balance for"),
                    ActionParameter("token_address", False, str, "Optional token address")
                ],
                description="Get $S or token balance"
            ),
            "transfer": Action(
                name="transfer",
                parameters=[
                    ActionParameter("to_address", True, str, "Recipient address"),
                    ActionParameter("amount", True, float, "Amount to transfer"),
                    ActionParameter("token_address", False, str, "Optional token address")
                ],
                description="Send $S or tokens"
            ),
            "swap": Action(
                name="swap",
                parameters=[
                    ActionParameter("token_in", True, str, "Input token address"),
                    ActionParameter("token_out", True, str, "Output token address"),
                    ActionParameter("amount", True, float, "Amount to swap"),
                    ActionParameter("slippage", False, float, "Max slippage percentage")
                ],
                description="Swap tokens"
            )
        }

    def configure(self) -> bool:
        logger.info("\n🔷 SONIC CHAIN SETUP")
        if self.is_configured():
            logger.info("Sonic connection is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            private_key = input("\nEnter your wallet private key: ")
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            set_key('.env', 'SONIC_PRIVATE_KEY', private_key)

            if not self._web3.is_connected() and not self.use_mock_mode:
                raise SonicConnectionError("Failed to connect to Sonic network")

            account = self._web3.eth.account.from_key(private_key)
            self.account = account
            logger.info(f"\n✅ Successfully connected with address: {account.address}")
            
            # Check balance after setup
            if not self.use_mock_mode:
                try:
                    balance = self._web3.eth.get_balance(account.address)
                    logger.info(f"Account balance: {self._web3.from_wei(balance, 'ether')} Sonic Tokens")
                except Exception as e:
                    logger.warning(f"Could not get account balance: {e}")
            
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        if self.use_mock_mode:
            return True
            
        try:
            load_dotenv()
            if not os.getenv('SONIC_PRIVATE_KEY'):
                if verbose:
                    logger.error("Missing SONIC_PRIVATE_KEY in .env")
                return False

            if not self._web3.is_connected():
                if verbose:
                    logger.error("Not connected to Sonic network")
                return False
            return True

        except Exception as e:
            if verbose:
                logger.error(f"Configuration check failed: {e}")
            return False

    # Enhanced transaction method with retry and better error handling
    def send_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a transaction to the blockchain with improved retry mechanism and error handling"""
        start_time = time.time()
        transaction_id = len(transaction_history) + 1
        tx_tag = f"[TX-{transaction_id}]"
        
        # Update transaction stats
        self.transaction_stats["sent"] += 1
        self.transaction_stats["last_tx_time"] = start_time
        
        # Log transaction request
        logger.info(f"{tx_tag} Preparing transaction: method={tx_data.get('method', 'unknown')}, args={tx_data.get('args', [])}")
        
        # Mock mode support
        if self.use_mock_mode:
            logger.info(f"{tx_tag} MOCK MODE: Simulated transaction for method {tx_data.get('method')}")
            
            # Simulate processing delay
            time.sleep(0.5)
            
            mock_result = {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,  # Mock transaction hash
                "transaction_url": "#mock-transaction",
                "mock": True,
                "gas_used": 100000,
                "effective_gas_price": self._web3.to_wei(10, 'gwei'),
                "execution_time": 0.5
            }
            
            # Store in transaction history
            transaction_history.append({
                "id": transaction_id,
                "type": "mock",
                "method": tx_data.get("method", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "result": mock_result
            })
            
            # Trim history if needed
            if len(transaction_history) > MAX_TRANSACTION_HISTORY:
                transaction_history.pop(0)
            
            # Update stats
            self.transaction_stats["successful"] += 1
            
            return mock_result
        
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                load_dotenv()
                if not self.account:
                    private_key = os.getenv('SONIC_PRIVATE_KEY')
                    if not private_key:
                        raise SonicConnectionError("Missing SONIC_PRIVATE_KEY in .env")
                    self.account = self._web3.eth.account.from_key(private_key)
                
                # Extract parameters from tx_data
                contract_address = tx_data.get("contract_address")
                method = tx_data.get("method")
                args = tx_data.get("args", [])
                
                # Get contract instance
                contract = None
                if contract_address == BERRY_TEMP_AGENT_ADDRESS:
                    contract = self.berry_temp_agent
                elif contract_address == BERRY_MANAGER_ADDRESS:
                    contract = self.berry_manager
                else:
                    contract = self._web3.eth.contract(
                        address=Web3.to_checksum_address(contract_address),
                        abi=self.ERC20_ABI
                    )
                
                if not contract:
                    raise SonicConnectionError(f"Contract not initialized for address: {contract_address}")
                
                # Get contract function
                contract_function = getattr(contract.functions, method)
                
                # Calculate nonce (increase with each retry to avoid nonce conflicts)
                nonce = self._web3.eth.get_transaction_count(self.account.address) + retry_count
                
                # Create transaction parameters
                tx_params = {
                    'from': self.account.address,
                    'nonce': nonce,
                    'chainId': self._web3.eth.chain_id
                }
                
                # Estimate gas and check funds
                gas_info = self._estimate_transaction_gas(tx_params, contract_function, args)
                
                if not gas_info["has_funds"]:
                    raise SonicConnectionError(
                        f"Insufficient funds for transaction. Have: {self._web3.from_wei(gas_info['balance'], 'ether')} tokens, "
                        f"Need: {self._web3.from_wei(gas_info['total_cost'], 'ether')} tokens"
                    )
                
                # Update transaction parameters with gas settings
                # Increase gas limit with each retry
                gas_limit = tx_data.get("gas_limit", self._safe_gas_estimation(tx_params, contract_function, args))
                gas_limit = int(gas_limit * (1 + (retry_count * 0.2)))
                
                # Use optimal gas price
                gas_price = self.get_optimal_gas_price()
                
                tx_params.update({
                    'gas': gas_limit,
                    'gasPrice': gas_price
                })
                
                # Build final transaction
                tx = contract_function(*args).build_transaction(tx_params)
                
                # Log transaction details
                logger.info(f"{tx_tag} Sending transaction: method={method}, gas={tx['gas']}, gasPrice={self._web3.from_wei(tx['gasPrice'], 'gwei')} gwei")
                
                # Sign and send transaction
                signed_tx = self.account.sign_transaction(tx)
                tx_hash = self._web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                # Wait for transaction to be mined with timeout and progress updates
                timeout = 120  # 2 minutes
                start_wait = time.time()
                receipt = None
                
                while time.time() - start_wait < timeout:
                    try:
                        receipt = self._web3.eth.get_transaction_receipt(tx_hash)
                        if receipt is not None:
                            break
                    except Exception:
                        pass
                    
                    # Print a waiting message every 10 seconds
                    if int(time.time() - start_wait) % 10 == 0:
                        elapsed = int(time.time() - start_wait)
                        logger.info(f"{tx_tag} Waiting for transaction to be mined... ({elapsed}s elapsed)")
                    
                    time.sleep(1)
                
                if receipt is None:
                    raise TimeoutError(f"Transaction not mined within {timeout} seconds")
                
                # Transaction successful
                execution_time = time.time() - start_time
                
                result = {
                    "success": receipt.status == 1,
                    "transaction_hash": tx_hash.hex(),
                    "transaction_url": self._get_explorer_link(tx_hash.hex()),
                    "gas_used": receipt.gasUsed,
                    "effective_gas_price": receipt.effectiveGasPrice if hasattr(receipt, 'effectiveGasPrice') else tx['gasPrice'],
                    "execution_time": execution_time
                }
                
                # Store in transaction history
                transaction_history.append({
                    "id": transaction_id,
                    "type": "blockchain",
                    "method": method,
                    "args": args,
                    "timestamp": datetime.now().isoformat(),
                    "result": result
                })
                
                # Trim history if needed
                if len(transaction_history) > MAX_TRANSACTION_HISTORY:
                    transaction_history.pop(0)
                
                # Update transaction stats
                if receipt.status == 1:
                    self.transaction_stats["successful"] += 1
                else:
                    self.transaction_stats["failed"] += 1
                
                self.transaction_stats["total_gas_used"] += receipt.gasUsed
                if self.transaction_stats["sent"] > 0:
                    self.transaction_stats["avg_gas_used"] = self.transaction_stats["total_gas_used"] / self.transaction_stats["sent"]
                
                # Calculate cost in tokens
                tx_cost = receipt.gasUsed * (receipt.effectiveGasPrice if hasattr(receipt, 'effectiveGasPrice') else tx['gasPrice'])
                tx_cost_eth = self._web3.from_wei(tx_cost, 'ether')
                self.transaction_stats["total_cost"] += float(tx_cost_eth)
                
                # Log success or failure
                if receipt.status == 1:
                    logger.info(f"{tx_tag} Transaction successful: Gas used: {receipt.gasUsed}, Cost: {tx_cost_eth} tokens, Time: {execution_time:.2f}s")
                else:
                    logger.warning(f"{tx_tag} Transaction failed on-chain: {tx_hash.hex()}")
                
                return result
                
            except Exception as e:
                retry_count += 1
                last_error = e
                
                # Check specific error types for better handling
                error_str = str(e).lower()
                if "nonce too low" in error_str or "replacement transaction underpriced" in error_str:
                    logger.warning(f"{tx_tag} Nonce issue detected: {e}")
                    # Refresh nonce on next attempt
                elif "insufficient funds" in error_str:
                    logger.error(f"{tx_tag} Insufficient funds error: {e}")
                    # This is not recoverable, so break retry loop
                    break
                elif "gas price too low" in error_str or "underpriced" in error_str:
                    logger.warning(f"{tx_tag} Gas price too low: {e}")
                    # Increase gas price multiplier on next attempt
                
                if retry_count < max_retries:
                    # Calculate delay with exponential backoff
                    delay = 2 ** retry_count
                    logger.warning(f"{tx_tag} Transaction attempt {retry_count} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"{tx_tag} All retry attempts failed: {e}", exc_info=True)
        
        # All retries failed
        execution_time = time.time() - start_time
        error_result = {
            "success": False,
            "error": str(last_error),
            "method": tx_data.get("method", "unknown"),
            "execution_time": execution_time
        }
        
        # Update failed transaction count
        self.transaction_stats["failed"] += 1
        
        # Store in transaction history
        transaction_history.append({
            "id": transaction_id,
            "type": "failed",
            "method": tx_data.get("method", "unknown"),
            "args": tx_data.get("args", []),
            "timestamp": datetime.now().isoformat(),
            "result": error_result,
            "error": str(last_error)
        })
        
        # Trim history if needed
        if len(transaction_history) > MAX_TRANSACTION_HISTORY:
            transaction_history.pop(0)
        
        logger.error(f"{tx_tag} Failed to send transaction after {max_retries} attempts: {last_error}")
        return error_result

    def call_contract(self, tx_data: Dict[str, Any]) -> Any:
        """Call a contract method (read-only) with improved error handling"""
        # Generate a tag for tracing this call
        call_id = f"CALL-{int(time.time())}"
        
        # Mock mode support
        if self.use_mock_mode:
            logger.info(f"[{call_id}] MOCK MODE: Simulated contract call for method {tx_data.get('method')}")
            # Return mock data based on the method
            method = tx_data.get("method")
            batch_id = tx_data.get("args", [0])[0] if tx_data.get("args") else 0
            
            if method == "getTemperatureHistory":
            # Create batch-specific temperature history
             mock_history = []
             for reading in self.mock_data["temperature_history"]:
                 if reading["batchId"] == batch_id:
            # Convert to list format expected by the contract
                    mock_history.append([
                    reading["timestamp"],
                    reading["temperature"],
                    reading["location"],
                    reading["temperature"] > 40 or reading["temperature"] < 0,  # isBreached
                    5 if (reading["temperature"] > 40 or reading["temperature"] < 0) else 0  # predictedImpact
            ])
             return mock_history
            
            elif method == "getBatchDetails":
                # Mock batch details
                return [
                    batch_id,  # batchId
                    "Strawberry",  # berryType
                    int(datetime.now().timestamp()) - 86400,  # startTime
                    0,  # endTime
                    True,  # isActive
                    1,  # status (1 = InTransit)
                    85,  # qualityScore
                    60 * 60 * 60  # predictedShelfLife (60 hours in seconds)
                ]
                
            elif method == "getAgentPredictions":
                # Mock predictions
                return [
                    [
                        int(datetime.now().timestamp()) - 1800,  # timestamp
                        85,  # predictedQuality
                        3,  # recommendedAction
                        "Monitor closely. Continue with standard delivery procedures."  # actionDescription
                    ]
                ]
                
            elif method == "getSupplierDetails":
                # Mock supplier details
                return [
                    "0x" + "1" * 40,  # account
                    True,  # isRegistered
                    85,  # reputation
                    12,  # totalBatches
                    10,  # successfulBatches
                    int(datetime.now().timestamp()) - 3600  # lastActionTime
                ]
                
            elif method == "batchCount":
                # Mock batch count
                return batch_id + 1
                
            # Default mock return
            return []
        
        # Real contract call
        try:
            start_time = time.time()
            logger.info(f"[{call_id}] Calling contract method: {tx_data.get('method')}, args: {tx_data.get('args', [])}")
            
            # Extract parameters from tx_data
            contract_address = tx_data.get("contract_address")
            method = tx_data.get("method")
            args = tx_data.get("args", [])
            
            # Get contract instance
            contract = None
            if contract_address == BERRY_TEMP_AGENT_ADDRESS:
                contract = self.berry_temp_agent
            elif contract_address == BERRY_MANAGER_ADDRESS:
                contract = self.berry_manager
            else:
                try:
                    contract = self._web3.eth.contract(
                        address=Web3.to_checksum_address(contract_address),
                        abi=self.ERC20_ABI
                    )
                except Exception as e:
                    logger.error(f"[{call_id}] Error creating contract instance: {e}")
                    raise
            
            if not contract:
                error_msg = f"Contract not initialized for address: {contract_address}"
                logger.error(f"[{call_id}] {error_msg}")
                raise SonicConnectionError(error_msg)
            
            # Get contract function
            try:
                contract_function = getattr(contract.functions, method)
            except AttributeError as e:
                logger.error(f"[{call_id}] Method not found: {method}")
                raise SonicConnectionError(f"Method {method} not found on contract") from e
            
            # Call the function with retry logic
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    # Call the function
                    result = contract_function(*args).call()
                    
                    # Log success
                    execution_time = time.time() - start_time
                    logger.info(f"[{call_id}] Contract call successful in {execution_time:.2f}s")
                    
                    return result
                    
                except Exception as e:
                    retry_count += 1
                    last_error = e
                    
                    if retry_count < max_retries:
                        # Calculate delay with exponential backoff
                        delay = 2 ** retry_count
                        logger.warning(f"[{call_id}] Contract call attempt {retry_count} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"[{call_id}] All retry attempts failed: {e}")
            
            # All retries failed
            logger.error(f"[{call_id}] Failed to call contract after {max_retries} attempts: {last_error}")
            raise last_error
                
        except Exception as e:
            logger.error(f"[{call_id}] Failed to call contract: {e}", exc_info=True)
            
            if self.use_mock_mode:
                logger.warning(f"[{call_id}] Error in mock mode, returning empty result")
                return []
                
            raise

    # Berry contract interaction methods with improved error handling
    def create_batch(self, berry_type: str) -> Dict[str, Any]:
        """Create a new berry batch"""
        logger.info(f"Creating new batch for berry type: {berry_type}")
        
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Creating batch for berry type: {berry_type}")
            return {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,
                "transaction_url": "#mock-transaction",
                "batch_id": 1,
                "berry_type": berry_type,
                "mock": True
            }
            
        try:
            if not self.berry_temp_agent:
                raise SonicConnectionError("BerryTempAgent contract not initialized")
            
            # Use send_transaction method with proper gas handling
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "createBatch",
                "args": [berry_type],
                "gas_limit": 300000
            }
            
            result = self.send_transaction(tx_data)
            
            if result.get("success", False):
                try:
                    # Get batch count to determine batch ID
                    batch_count = self.berry_temp_agent.functions.batchCount().call()
                    batch_id = batch_count - 1
                    result["batch_id"] = batch_id
                except Exception as e:
                    logger.warning(f"Could not get batch ID: {e}")
                    result["batch_id"] = 0
                    
                result["berry_type"] = berry_type
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create batch: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "berry_type": berry_type
            }

    def record_temperature(self, batch_id: int, temperature: int, location: str) -> Dict[str, Any]:
        """Record temperature for a berry batch"""
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Recording temperature {temperature/10.0}°C at {location} for batch {batch_id}")
            return {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,
                "transaction_url": "#mock-transaction",
                "batch_id": batch_id,
                "temperature": temperature,
                "location": location,
                "mock": True
            }
            
        try:
            if not self.berry_temp_agent:
                raise SonicConnectionError("BerryTempAgent contract not initialized")
            
            # Use send_transaction method with proper gas handling
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "recordTemperature",
                "args": [batch_id, temperature, location],
                "gas_limit": 300000
            }
            
            result = self.send_transaction(tx_data)
            
            if result.get("success", False):
                result["batch_id"] = batch_id
                result["temperature"] = temperature
                result["location"] = location
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to record temperature: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id,
                "temperature": temperature,
                "location": location
            }
        def get_batch_details(self, batch_id: int) -> Dict[str, Any]:
            """Get details for a berry batch"""
            if self.use_mock_mode:
                logger.info(f"MOCK MODE: Getting details for batch {batch_id}")
                return {
                    "batchId": batch_id,
                    "berryType": "Strawberry",
                    "startTime": int(datetime.now().timestamp()) - 86400,
                    "endTime": 0,
                    "isActive": True,
                    "status": 1,  # 1 = InTransit
                    "qualityScore": 85,
                    "predictedShelfLife": 60 * 60 * 60  # 60 hours in seconds
                }
                
            try:
                if not self.berry_temp_agent:
                    raise SonicConnectionError("BerryTempAgent contract not initialized")
                
                # Use call_contract method
                tx_data = {
                    "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                    "method": "getBatchDetails",
                    "args": [batch_id]
                }
                
                batch = self.call_contract(tx_data)
                
                # Format batch data
                batch_data = {
                    "batchId": batch[0],
                    "berryType": batch[1],
                    "startTime": batch[2],
                    "endTime": batch[3],
                    "isActive": batch[4],
                    "status": batch[5],
                    "qualityScore": batch[6],
                    "predictedShelfLife": batch[7]
                }
                
                return batch_data
                
            except Exception as e:
                logger.error(f"Failed to get batch details: {e}")
                return {
                    "error": str(e),
                    "batchId": batch_id,
                    "berryType": "Unknown",
                    "isActive": False,
                    "qualityScore": 0
                }

    def get_temperature_history(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get temperature history for a berry batch"""
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Getting temperature history for batch {batch_id}")
            # Mock temperature history
            mock_history = []
            base_time = datetime.now() - timedelta(hours=12)
            
            for i in range(6):
                # Generate varying temperatures
                if i == 3:  # Create a breach in the middle
                    temp = 5.2
                else:
                    temp = 2.0 + (i % 3)
                
                # Generate locations
                locations = ["Cold Storage", "Loading Dock", "Transport", "Transport", "Transport", "Delivery Center"]
                
                mock_history.append({
                    "timestamp": int((base_time + timedelta(hours=i*2)).timestamp()),
                    "temperature": int(temp * 10),
                    "location": locations[i],
                    "isBreached": temp > 4.0 or temp < 0.0,
                    "predictedImpact": 5 if (temp > 4.0 or temp < 0.0) else 0
                })
            
            return mock_history
            
        try:
            if not self.berry_temp_agent:
                raise SonicConnectionError("BerryTempAgent contract not initialized")
            
            # Use call_contract method
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getTemperatureHistory",
                "args": [batch_id]
            }
            
            history = self.call_contract(tx_data)
            
            # Format temperature readings
            formatted_history = []
            for reading in history:
                formatted_history.append({
                    "timestamp": reading[0],
                    "temperature": reading[1],
                    "location": reading[2],
                    "isBreached": reading[3],
                    "predictedImpact": reading[4]
                })
                
            return formatted_history
            
        except Exception as e:
            logger.error(f"Failed to get temperature history: {e}")
            return []

    def get_agent_predictions(self, batch_id: int) -> List[Dict[str, Any]]:
        """Get agent predictions for a berry batch"""
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Getting agent predictions for batch {batch_id}")
            return [{
                "timestamp": int(datetime.now().timestamp()) - 1800,
                "predictedQuality": 85,
                "recommendedAction": 3,
                "actionDescription": "Monitor closely. Continue with standard delivery procedures."
            }]
            
        try:
            if not self.berry_temp_agent:
                raise SonicConnectionError("BerryTempAgent contract not initialized")
            
            # Use call_contract method
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getAgentPredictions",
                "args": [batch_id]
            }
            
            predictions = self.call_contract(tx_data)
            
            # Format predictions
            formatted_predictions = []
            for prediction in predictions:
                formatted_predictions.append({
                    "timestamp": prediction[0],
                    "predictedQuality": prediction[1],
                    "recommendedAction": prediction[2],
                    "actionDescription": prediction[3]
                })
                
            return formatted_predictions
            
        except Exception as e:
            logger.error(f"Failed to get agent predictions: {e}")
            return []

    def register_supplier(self) -> Dict[str, Any]:
        """Register as a supplier"""
        if self.use_mock_mode:
            logger.info("MOCK MODE: Registering supplier")
            return {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,
                "transaction_url": "#mock-transaction",
                "supplier": "0x" + "1" * 40,
                "mock": True
            }
            
        try:
            if not self.berry_manager:
                raise SonicConnectionError("BerryManager contract not initialized")
            
            # Use send_transaction method with proper gas handling
            tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "registerSupplier",
                "args": [],
                "gas_limit": 200000
            }
            
            result = self.send_transaction(tx_data)
            
            if result.get("success", False) and self.account:
                result["supplier"] = self.account.address
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to register supplier: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def process_agent_recommendation(self, batch_id: int) -> Dict[str, Any]:
        """Process agent recommendation for a batch"""
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Processing agent recommendation for batch {batch_id}")
            return {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,
                "transaction_url": "#mock-transaction",
                "batch_id": batch_id,
                "mock": True
            }
            
        try:
            if not self.berry_manager:
                raise SonicConnectionError("BerryManager contract not initialized")
            
            # Check if supplier is registered first
            supplier_details = self.get_supplier_details()
            if not supplier_details.get("isRegistered", False):
                logger.warning("Supplier not registered, attempting to register first")
                register_result = self.register_supplier()
                if not register_result.get("success", False):
                    raise SonicConnectionError("Failed to register supplier before processing recommendation")
            
            # Use send_transaction method with proper gas handling
            tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "processAgentRecommendation",
                "args": [batch_id],
                "gas_limit": 500000
            }
            
            result = self.send_transaction(tx_data)
            
            if result.get("success", False):
                result["batch_id"] = batch_id
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process agent recommendation: {e}")
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id
            }

    def get_supplier_details(self, supplier_address: Optional[str] = None) -> Dict[str, Any]:
        """Get supplier details"""
        if self.use_mock_mode:
            logger.info("MOCK MODE: Getting supplier details")
            return {
                "account": supplier_address or "0x" + "1" * 40,
                "isRegistered": True,
                "reputation": 85,
                "totalBatches": 12,
                "successfulBatches": 10,
                "lastActionTime": int(datetime.now().timestamp()) - 3600
            }
            
        try:
            if not self.berry_manager:
                raise SonicConnectionError("BerryManager contract not initialized")
            
            if not supplier_address and self.account:
                supplier_address = self.account.address
            elif not supplier_address:
                private_key = os.getenv('SONIC_PRIVATE_KEY')
                account = self._web3.eth.account.from_key(private_key)
                supplier_address = account.address
            
            # Use call_contract method
            tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "getSupplierDetails",
                "args": [supplier_address]
            }
            
            details = self.call_contract(tx_data)
            
            # Format supplier data
            supplier_data = {
                "account": details[0],
                "isRegistered": details[1],
                "reputation": details[2],
                "totalBatches": details[3],
                "successfulBatches": details[4],
                "lastActionTime": details[5]
            }
            
            return supplier_data
            
        except Exception as e:
            logger.error(f"Failed to get supplier details: {e}")
            return {
                "account": supplier_address or "Unknown",
                "isRegistered": False,
                "reputation": 0,
                "error": str(e)
            }

    def complete_shipment(self, batch_id: int) -> Dict[str, Any]:
        """Complete a shipment"""
        if self.use_mock_mode:
            logger.info(f"MOCK MODE: Completing shipment for batch {batch_id}")
            return {
                "success": True,
                "transaction_hash": "0x" + "0" * 64,
                "transaction_url": "#mock-transaction",
                "batch_id": batch_id,
                "mock": True
            }
            
        try:
            if not self.berry_manager:
                raise SonicConnectionError("BerryManager contract not initialized")
            
            # Use send_transaction method with proper gas handling
            tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "completeShipment",
                "args": [batch_id],
                "gas_limit": 400000
            }
            
            result = self.send_transaction(tx_data)
            
            if result.get("success", False):
                result["batch_id"] = batch_id
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to complete shipment: {e}")
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id
            }
    
    # Action handler methods with improved error handling
    def monitor_berry_temperature(self, **kwargs) -> Dict[str, Any]:
        """Monitor and analyze temperature data for berry shipments"""
        try:
            batch_id = kwargs.get("batch_id", 0)
            temperature = kwargs.get("temperature", 2.5)
            location = kwargs.get("location", "Unknown")
            
            # Convert temperature to integer with 1 decimal precision (* 10)
            temp_int = int(temperature * 10)
            
            logger.info(f"Monitoring temperature for batch {batch_id}: {temperature}°C at {location}")
            
            # Check account balance before proceeding (if not in mock mode)
            if not self.use_mock_mode and self.account:
                try:
                    balance = self._web3.eth.get_balance(self.account.address)
                    logger.info(f"Current balance: {self._web3.from_wei(balance, 'ether')} Sonic Tokens")
                    
                    if balance == 0:
                        logger.warning("Account has zero balance! Transaction likely to fail.")
                except Exception as e:
                    logger.warning(f"Could not check balance: {e}")
            
            # Record temperature
            return self.record_temperature(batch_id, temp_int, location)
            
        except Exception as e:
            logger.error(f"Berry temperature monitoring failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "batch_id": kwargs.get("batch_id", 0),
                "temperature": kwargs.get("temperature", 0),
                "location": kwargs.get("location", "")
            }
    
    def manage_berry_quality(self, **kwargs) -> Dict[str, Any]:
        """Assess and predict berry quality based on temperature history"""
        try:
            batch_id = kwargs.get("batch_id", 0)
            
            # Get batch details
            batch_details = self.get_batch_details(batch_id)
            
            # Get temperature history
            temp_history = self.get_temperature_history(batch_id)
            
            # Get agent predictions
            predictions = self.get_agent_predictions(batch_id)
            
            return {
                "batch_details": batch_details,
                "temperature_history": temp_history,
                "predictions": predictions
            }
        except Exception as e:
            logger.error(f"Berry quality management failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "batch_id": kwargs.get("batch_id", 0)
            }
    
    def process_agent_recommendations(self, **kwargs) -> Dict[str, Any]:
        """Process agent recommendations and update supplier reputation"""
        try:
            batch_id = kwargs.get("batch_id")
            return self.process_agent_recommendation(batch_id)
        except Exception as e:
            logger.error(f"Processing agent recommendations failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "batch_id": kwargs.get("batch_id", 0)
            }
    
    def manage_batch_lifecycle(self, **kwargs) -> Dict[str, Any]:
        """Manage berry batch lifecycle from creation to delivery"""
        try:
            action = kwargs.get("action")
            batch_id = kwargs.get("batch_id", 0)
            berry_type = kwargs.get("berry_type", "Strawberry")
            
            if action == "create":
                return self.create_batch(berry_type)
            elif action == "complete":
                return self.complete_shipment(batch_id)
            elif action == "status":
                return self.get_batch_details(batch_id)
            elif action == "report":
                # Get batch details and temperature history for a comprehensive report
                batch_details = self.get_batch_details(batch_id)
                temp_history = self.get_temperature_history(batch_id)
                predictions = self.get_agent_predictions(batch_id)
                
                return {
                    "success": True,
                    "batch_id": batch_id,
                    "batch_details": batch_details,
                    "temperature_history": temp_history,
                    "predictions": predictions
                }
            else:
                raise ValueError(f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Batch lifecycle management failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "action": kwargs.get("action", ""),
                "batch_id": kwargs.get("batch_id", 0)
            }
    
    def system_health_check(self, **kwargs) -> Dict[str, Any]:
        """Perform system health check"""
        try:
            # Check blockchain connection
            is_connected = self._web3.is_connected() if not self.use_mock_mode else True
            
            # Check account balance
            balance = 0
            if self.account and not self.use_mock_mode:
                balance = self._web3.eth.get_balance(self.account.address)
            
            # Check contract accessibility
            contract_accessible = False
            try:
                if self.berry_temp_agent:
                    batch_count = self.berry_temp_agent.functions.batchCount().call()
                    contract_accessible = True
            except Exception:
                pass
            
            # Generate health report
            return {
                "success": True,
                "is_connected": is_connected,
                "contract_accessible": contract_accessible,
                "account_balance": balance,
                "account_balance_formatted": str(self._web3.from_wei(balance, 'ether')) if balance > 0 else "0",
                "transaction_stats": self.transaction_stats,
                "mock_mode": self.use_mock_mode
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def manage_batch_sequence(self, **kwargs) -> Dict[str, Any]:
        """Execute a batch sequence of operations"""
        try:
            # This function would orchestrate a sequence of operations
            # Create batch, record temperatures, assess quality, etc.
            batch_id = kwargs.get("batch_id", 0)
            berry_type = kwargs.get("berry_type", "Strawberry")
            
            # Start with creating a batch if no batch_id provided
            if batch_id == 0 and "batch_id" not in kwargs:
                create_result = self.create_batch(berry_type)
                if not create_result.get("success", False):
                    return create_result
                
                batch_id = create_result.get("batch_id", 0)
            
            # Record a temperature
            temp = kwargs.get("temperature", 2.5)
            location = kwargs.get("location", "Transport")
            temp_result = self.record_temperature(batch_id, int(temp * 10), location)
            
            # Get batch details
            batch_details = self.get_batch_details(batch_id)
            
            return {
                "success": True,
                "batch_id": batch_id,
                "temperature_recorded": temp_result.get("success", False),
                "batch_details": batch_details
            }
            
        except Exception as e:
            logger.error(f"Batch sequence management failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Sonic action with validation"""
        if action_name not in self.actions:
            return {
                "success": False,
                "error": f"Unknown action: {action_name}"
            }

        load_dotenv()
        
        if not self.is_configured(verbose=True) and not self.use_mock_mode:
            return {
                "success": False,
                "error": "Sonic is not properly configured"
            }

        # Log action details for debugging
        logger.info(f"Executing action '{action_name}' with parameters: {kwargs}")
        
        # Check account balance before proceeding with any action
        if self.account and not self.use_mock_mode:
            try:
                balance = self._web3.eth.get_balance(self.account.address)
                logger.info(f"Current account balance: {self._web3.from_wei(balance, 'ether')} Sonic Tokens")
                
                if balance == 0:
                    logger.warning("Account has zero balance! Transactions likely to fail.")
            except Exception as e:
                logger.warning(f"Could not check balance: {e}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            return {
                "success": False,
                "error": f"Invalid parameters: {', '.join(errors)}"
            }

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        
        try:
            result = method(**kwargs)
            logger.info(f"Action '{action_name}' completed successfully")
            return result
        except Exception as e:
            logger.error(f"Action '{action_name}' failed: {e}", exc_info=True)
            # Return error information instead of raising
            return {
                "success": False,
                "error": str(e),
                "action": action_name,
                "parameters": kwargs
            }
    
    def get_transaction_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transaction history"""
        if limit > MAX_TRANSACTION_HISTORY:
            limit = MAX_TRANSACTION_HISTORY
            
        return transaction_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = {
            "transactions": self.transaction_stats,
            "connection": {
                "network": self.network_name,
                "mock_mode": self.use_mock_mode,
                "is_connected": self._web3.is_connected() if not self.use_mock_mode else True,
                "contracts_loaded": len(self.contract_instances)
            }
        }
        
        # Add account stats if available
        if self.account:
            try:
                balance = 0
                if not self.use_mock_mode:
                    balance = self._web3.eth.get_balance(self.account.address)
                    
                stats["account"] = {
                    "address": self.account.address,
                    "balance": str(self._web3.from_wei(balance, 'ether')),
                    "balance_wei": str(balance)
                }
            except Exception as e:
                logger.warning(f"Could not get account stats: {e}")
                stats["account"] = {
                    "address": self.account.address,
                    "error": str(e)
                }
        
        return stats