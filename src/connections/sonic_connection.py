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
from src.connections.anthropic_connection import AnthropicConnection
from src.constants.networks import SONIC_NETWORKS
from src.connections.base_connection import BaseConnection, Action, ActionParameter

# Configure logging
logger = logging.getLogger("connections.sonic_connection")
file_handler = logging.FileHandler("sonic_connection.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
logger.addHandler(file_handler)

# Contract addresses
BERRY_TEMP_AGENT_ADDRESS = "0x428bC2B646B3CfeD15699fBaf66688F928f80f56"
BERRY_MANAGER_ADDRESS = "0x70C0899d28Bf93D1cA1D36aE7f3c158Fecb6CAE9"

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
        
        # Reference to the parent agent (set by connection manager)
        self.agent = None
        
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

    def perform_action(self, action_name: str, kwargs: Dict[str, Any]) -> Any:
        """Execute a Sonic action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = []
        
        # Validate parameters if they are provided
        if kwargs:
            errors = action.validate_params(kwargs)
        
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        if not hasattr(self, method_name):
            raise AttributeError(f"Method {method_name} not found on SonicConnection")
        
        method = getattr(self, method_name)
        
        # Log the action being performed
        logger.info(f"Executing action {action_name} with parameters: {kwargs}")
        
        # Call the method with the provided parameters
        try:
            return method(**kwargs)
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {str(e)}", exc_info=True)
            raise

    def analyze_text_with_llm(self, prompt: str, system_prompt: str = None, model: str = None):
        """Use AnthropicConnection capabilities to analyze text"""
        try:
            # Access the AnthropicConnection through the agent
            if hasattr(self, 'agent') and hasattr(self.agent, 'connection_manager'):
                anthropic_conn = self.agent.connection_manager.connections.get('anthropic')
                
                if anthropic_conn and isinstance(anthropic_conn, AnthropicConnection):
                    # If no system prompt provided, use a default focused on berry analysis
                    if not system_prompt:
                        system_prompt = """You are a specialized AI assistant for berry supply chain monitoring.
                        Your expertise includes cold chain management, temperature-sensitive produce handling,
                        quality assessment, and shelf-life prediction for berries.
                        Provide data-driven, accurate analysis with practical recommendations."""
                    
                    # Use the generate_text method from AnthropicConnection
                    return anthropic_conn.generate_text(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        model=model or anthropic_conn.config.get("model")
                    )
            
            # Fallback if AnthropicConnection is not available
            logger.warning("AnthropicConnection not available, using mock response")
            return "Analysis not available without AnthropicConnection"
            
        except Exception as e:
            logger.error(f"Failed to analyze text with LLM: {e}", exc_info=True)
            return f"Error analyzing text: {str(e)}"

    def monitor_berry_temperature(self, batch_id: int, temperature: float, location: str) -> Dict[str, Any]:
        """Monitor and analyze temperature data for berry shipments"""
        try:
            logger.info(f"Monitoring temperature for batch {batch_id}: {temperature}°C at {location}")
            
            # Convert temperature to integer representation as expected by the contract (multiplied by 10)
            temp_int = int(temperature * 10)
            
            # Call record_temperature method which handles the blockchain interaction
            result = self.record_temperature(batch_id, temp_int, location)
            
            # Analyze temperature data
            is_breach = temperature > 4.0 or temperature < 0.0
            severity = "None"
            
            if is_breach:
                if temperature > 6.0 or temperature < -1.0:
                    severity = "Critical"
                else:
                    severity = "Warning"
                    
            # Add analysis to result
            result.update({
                "analysis": {
                    "is_breach": is_breach,
                    "severity": severity,
                    "optimal_range": "0.0°C - 4.0°C",
                    "recommendation": self._generate_recommendation(temperature, is_breach, severity)
                }
            })
            
            return result
        except Exception as e:
            logger.error(f"Failed to monitor temperature: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id,
                "temperature": temperature,
                "location": location
            }
            
    def _generate_recommendation(self, temperature: float, is_breach: bool, severity: str) -> str:
        """Generate a recommendation based on temperature data"""
        if not is_breach:
            return "Temperature within acceptable range. Continue standard monitoring."
        elif severity == "Warning":
            return f"Temperature ({temperature}°C) outside optimal range. Increase monitoring frequency and check cooling systems."
        else:  # Critical
            return f"Critical temperature breach ({temperature}°C). Immediate intervention required. Consider moving product to alternative cold storage."

    def manage_berry_quality(self, batch_id: int) -> Dict[str, Any]:
        """Assess and predict berry quality based on temperature history"""
        try:
            logger.info(f"Assessing quality for batch {batch_id}")
        
            # Get temperature history
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getTemperatureHistory",
                "args": [batch_id]
            }
        
            temp_history = self.call_contract(tx_data)
        
            # Get batch details
            batch_details = self.get_batch_details(batch_id)
        
            # Calculate quality score and shelf life
            quality_score = 100
            shelf_life_hours = 72  # Default
        
            # Process temperature readings
            breach_count = 0
            reading_count = len(temp_history) if temp_history else 0
        
            for reading in temp_history or []:
                # Extract temperature (handle different data formats)
                if isinstance(reading, tuple):
                    # Extract temperature from tuple format
                    temp = reading[1] / 10.0 if len(reading) > 1 else 0
                elif isinstance(reading, list):
                    # Extract temperature from list format
                    temp = reading[1] / 10.0 if len(reading) > 1 else 0
                elif isinstance(reading, dict):
                    # Extract temperature from dictionary format
                    temp = reading.get("temperature", 0)
                else:
                    # Default case if format is unknown
                    temp = 0
                    logger.warning(f"Unknown temperature reading format: {type(reading)}")
                
                # Check for breaches
                if temp > 4.0:
                    breach_count += 1
                    deviation = temp - 4.0
                    quality_score -= deviation * 5
                    shelf_life_hours -= deviation * 4
                elif temp < 0.0:
                    breach_count += 1
                    deviation = 0.0 - temp
                    quality_score -= deviation * 7
                    shelf_life_hours -= deviation * 6
        
                # Ensure values don't go below zero
                quality_score = max(0, quality_score)
                shelf_life_hours = max(0, shelf_life_hours)
        
            # Determine recommended action
            action = "No Action"
            if quality_score < 60:
                action = "Reject"
            elif quality_score < 70:
                action = "Reroute"
            elif quality_score < 80:
                action = "Expedite"
            elif quality_score < 90:
                action = "Alert"
            
            return {
                "success": True,
                "batch_id": batch_id,
                "berry_type": batch_details.get("berryType", "Unknown"),
                "quality_score": round(quality_score, 1),
                "shelf_life_hours": round(shelf_life_hours, 1),
                "breach_count": breach_count,
                "reading_count": reading_count,
                "breach_percentage": round((breach_count / reading_count * 100) if reading_count > 0 else 0, 1),
                "recommended_action": action
            }
        except Exception as e:
            logger.error(f"Failed to assess quality: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id
            }

    def process_agent_recommendations(self, batch_id: int) -> Dict[str, Any]:
        """Process agent recommendations and update supplier reputation"""
        try:
            logger.info(f"Processing recommendations for batch {batch_id}")
            
            # Call contract method
            tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "processAgentRecommendation",
                "args": [batch_id],
                "gas_limit": 500000
            }
            
            result = self.send_transaction(tx_data)
            
            # Get supplier details
            supplier_tx_data = {
                "contract_address": BERRY_MANAGER_ADDRESS,
                "method": "getSupplierDetails",
                "args": [self.account.address if self.account else "0x0"]
            }
            
            supplier_details = self.call_contract(supplier_tx_data)
            
            # Format supplier details
            if supplier_details:
                supplier_info = {
                    "account": supplier_details[0] if len(supplier_details) > 0 else "Unknown",
                    "reputation": supplier_details[2] if len(supplier_details) > 2 else 0,
                    "total_batches": supplier_details[3] if len(supplier_details) > 3 else 0,
                    "successful_batches": supplier_details[4] if len(supplier_details) > 4 else 0
                }
                result.update({"supplier_info": supplier_info})
                
            return result
        except Exception as e:
            logger.error(f"Failed to process recommendations: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "batch_id": batch_id
            }

    def manage_batch_lifecycle(self, action: str, batch_id: int = None, berry_type: str = None) -> Dict[str, Any]:
        """Manage berry batch lifecycle from creation to delivery"""
        try:
            logger.info(f"Managing batch lifecycle: {action}")
            
            if action == "create":
                if not berry_type:
                    berry_type = "Strawberry"  # Default
                return self.create_batch(berry_type)
                
            elif action == "complete":
                batch_tag = f"[Batch #{batch_id}]"
                logger.info(f"{batch_tag} Shipment completion is now handled via frontend")
                    
                # Call contract method
                return {
                    "success": False,
                    "action": "complete",
                    "batch_id": batch_id,
                    "message": "Shipment completion is now handled directly through the frontend interface",
                    "manual_action_required": True
                    
                }
                
                
            elif action == "status":
                if batch_id is None:
                    raise ValueError("batch_id is required for status action")
                    
                return self.get_batch_details(batch_id)
                
            elif action == "report":
                if batch_id is None:
                    raise ValueError("batch_id is required for report action")
                    
                # Get batch details
                batch_details = self.get_batch_details(batch_id)
                
                # Get temperature history
                tx_data = {
                    "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                    "method": "getTemperatureHistory",
                    "args": [batch_id]
                }
                
                temp_history = self.call_contract(tx_data)
                
                # Format temperature history
                formatted_history = []
                for reading in temp_history or []:
                    if isinstance(reading, list):
                        formatted_reading = {
                            "timestamp": reading[0] if len(reading) > 0 else 0,
                            "temperature": reading[1]/10.0 if len(reading) > 1 else 0,
                            "location": reading[2] if len(reading) > 2 else "Unknown",
                            "is_breach": reading[3] if len(reading) > 3 else False
                        }
                    else:
                        formatted_reading = reading
                        
                    formatted_history.append(formatted_reading)
                    
                # Combine data into report
                report = {
                    "batch_details": batch_details,
                    "temperature_history": formatted_history[:10],  # Include first 10 readings
                    "reading_count": len(temp_history or [])
                }
                
                return {
                    "success": True,
                    "batch_id": batch_id,
                    "report": report
                }
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            logger.error(f"Failed to manage batch lifecycle: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "action": action,
                "batch_id": batch_id
            }

    def system_health_check(self, reset_counters: bool = False) -> Dict[str, Any]:
        """Perform a system health check and return metrics"""
        try:
            logger.info("Performing system health check")
            
            # Check connection status
            is_connected = self._web3.is_connected() if not self.use_mock_mode else True
            
            # Check account balance
            balance = 0
            if self.account and not self.use_mock_mode:
                balance = self._web3.eth.get_balance(self.account.address)
                
            # Calculate transaction success rate
            success_rate = 0
            if self.transaction_stats["sent"] > 0:
                success_rate = (self.transaction_stats["successful"] / self.transaction_stats["sent"]) * 100
                
            # Reset counters if requested
            if reset_counters:
                self.transaction_stats = {
                    "sent": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_gas_used": 0,
                    "avg_gas_used": 0,
                    "last_tx_time": None,
                    "total_cost": 0
                }
                
            # Assemble health report
            health_report = {
                "timestamp": datetime.now().isoformat(),
                "connection": {
                    "is_connected": is_connected,
                    "network": self.network_name,
                    "account": self.account.address if self.account else None,
                    "balance": self._web3.from_wei(balance, 'ether') if balance > 0 else 0
                },
                "transactions": {
                    "sent": self.transaction_stats["sent"],
                    "successful": self.transaction_stats["successful"],
                    "failed": self.transaction_stats["failed"],
                    "success_rate": f"{success_rate:.2f}%",
                    "total_gas_used": self.transaction_stats["total_gas_used"],
                    "avg_gas_used": self.transaction_stats["avg_gas_used"],
                    "total_cost": f"{self.transaction_stats['total_cost']:.6f} Sonic Tokens"
                },
                "counters_reset": reset_counters
            }
            
            return {
                "success": True,
                "health_report": health_report
            }
        except Exception as e:
            logger.error(f"Failed to perform health check: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def manage_batch_sequence(self, berry_type: str = None, temperatures: List[float] = None, 
                             locations: List[str] = None, complete_shipment: bool = False) -> Dict[str, Any]:
        """Execute a complete batch lifecycle sequence"""
        try:
            logger.info("Executing batch sequence")
            
            # Set defaults if not provided
            if not berry_type:
                berry_type = "Strawberry"
                
            if not temperatures:
                temperatures = [2.0, 2.5, 3.0, 3.5, 2.8, 2.2]
                
            if not locations:
                locations = ["Cold Storage", "Loading Dock", "Transport", "Transport", "Transport", "Delivery"]
                
            # Step 1: Create batch
            create_result = self.manage_batch_lifecycle(action="create", berry_type=berry_type)
            
            if not create_result.get("success", False):
                raise Exception(f"Failed to create batch: {create_result.get('error', 'Unknown error')}")
                
            batch_id = create_result.get("batch_id", 0)
            
            # Step 2: Record temperatures
            temp_results = []
            for temp, location in zip(temperatures, locations):
                temp_result = self.monitor_berry_temperature(batch_id, temp, location)
                temp_results.append(temp_result)
                time.sleep(1)  # Small delay to avoid transaction collisions
                
            # Step 3: Assess quality
            quality_result = self.manage_berry_quality(batch_id)
            
            # Step 4: Process recommendations
            rec_result = self.process_agent_recommendations(batch_id)
            
            # Step 5: Complete shipment if requested
            complete_result = None
            if complete_shipment:
               logger.info(f"Batch {batch_id}: Shipment completion should be done via frontend")
               complete_result = {
                        "success": False,
                        "message": "Shipment completion is now handled directly through the frontend interface",
                        "manual_action_required": True
                     }
                
            # Step 6: Generate report
            report_result = self.manage_batch_lifecycle(action="report", batch_id=batch_id)
            
            return {
                "success": True,
                "batch_id": batch_id,
                "berry_type": berry_type,
                "temperature_count": len(temp_results),
                "quality_result": quality_result,
                "complete_shipment": complete_shipment,
                "complete_result": complete_result,
                "report": report_result.get("report", {})
            }
        except Exception as e:
            logger.error(f"Failed to execute batch sequence: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
            
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
            
            # Check if abis directory exists
            abi_dir = os.path.join(project_root, "abis")
            if not os.path.exists(abi_dir):
                logger.warning(f"ABIs directory not found at {abi_dir}")
                
                # Try alternative locations
                alt_locations = [
                    os.path.join(project_root, "..", "abis"),
                    os.path.join(project_root, "src", "abis"),
                    os.path.join(project_root, "contract-abis")
                ]
                
                for loc in alt_locations:
                    if os.path.exists(loc):
                        abi_dir = loc
                        logger.info(f"Found ABIs directory at alternative location: {abi_dir}")
                        break
            else:
                logger.info(f"Found ABIs directory at: {abi_dir}")
            
            # List of contracts to load
            contracts_to_load = [
                {
                    "name": "BerryTempAgent",
                    "path": os.path.join(abi_dir, "BerryTempAgent.json"),
                    "address": BERRY_TEMP_AGENT_ADDRESS
                },
                {
                    "name": "BerryManager",
                    "path": os.path.join(abi_dir, "BerryManager.json"),
                    "address": BERRY_MANAGER_ADDRESS
                }
            ]
            
            # Try to load from combined file first
            combined_path = os.path.join(project_root, "contract-abis.json")
            combined_abis = None
            if os.path.exists(combined_path):
                try:
                    with open(combined_path, 'r') as f:
                        combined_abis = json.loads(f.read())
                    logger.info(f"Found combined ABIs file: {combined_path}")
                except Exception as e:
                    logger.warning(f"Error reading combined ABIs file: {e}")
            
            # Load each contract ABI
            for contract in contracts_to_load:
                try:
                    abi_path = contract["path"]
                    logger.info(f"Attempting to load {contract['name']} ABI from: {abi_path}")
                    
                    # First try to load from combined file if available
                    if combined_abis and contract["name"] in combined_abis:
                        self.contract_abis[contract["name"]] = combined_abis[contract["name"]]
                        logger.info(f"Loaded {contract['name']} ABI from combined file with {len(combined_abis[contract['name']])} entries")
                        continue
                    
                    if not os.path.exists(abi_path):
                        logger.warning(f"Contract artifact not found: {abi_path}")
                        continue
                        
                    with open(abi_path, 'r') as f:
                        abi_content = f.read()
                        # Debug log the first 100 chars to verify content
                        logger.debug(f"ABI file content starts with: {abi_content[:100]}...")
                        
                        contract_json = json.loads(abi_content)
                        
                    # Handle different ABI formats
                    if isinstance(contract_json, dict) and contract["name"] in contract_json:
                        # Handle format like {"BerryTempAgent": [...], "BerryManager": [...]}
                        self.contract_abis[contract["name"]] = contract_json[contract["name"]]
                        logger.info(f"Loaded ABI for {contract['name']} from named dictionary with {len(contract_json[contract['name']])} entries")
                    elif isinstance(contract_json, list):
                        # Direct ABI array
                        self.contract_abis[contract["name"]] = contract_json
                        logger.info(f"Loaded ABI array for {contract['name']} with {len(contract_json)} entries")
                    elif isinstance(contract_json, dict):
                        # Check for nested ABI structures
                        if "abi" in contract_json:
                            self.contract_abis[contract["name"]] = contract_json["abi"]
                            logger.info(f"Loaded nested ABI for {contract['name']} with {len(contract_json['abi'])} entries")
                        elif "bytecode" in contract_json or "deployedBytecode" in contract_json:
                            # This looks like a Hardhat/Truffle artifact but missing ABI
                            logger.warning(f"{contract['name']} appears to be a contract artifact but missing 'abi' field")
                            continue
                        else:
                            # Try to find any array that might be the ABI
                            for key, value in contract_json.items():
                                if isinstance(value, list) and len(value) > 0 and "type" in value[0]:
                                    self.contract_abis[contract["name"]] = value
                                    logger.info(f"Found potential ABI in '{key}' for {contract['name']}")
                                    break
                            else:
                                logger.warning(f"Could not identify ABI structure in {contract['name']} JSON")
                    else:
                        logger.warning(f"Unknown format for {contract['name']} ABI: {type(contract_json)}")
                        continue
                    
                    # Print available functions for debugging
                    if contract["name"] in self.contract_abis:
                        abi = self.contract_abis[contract["name"]]
                        functions = [item["name"] for item in abi if item.get("type") == "function"]
                        logger.info(f"{contract['name']} ABI contains functions: {', '.join(functions[:10])}{' and more...' if len(functions) > 10 else ''}")
                        
                        # Check for specific functions
                        if contract["name"] == "BerryTempAgent":
                            required_functions = ["createBatch", "batchCount", "getTemperatureHistory"]
                            for func in required_functions:
                                if func not in functions:
                                    logger.warning(f"Required function '{func}' not found in {contract['name']} ABI!")
                                else:
                                    logger.info(f"Found required function: {func}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing error in {contract['name']} ABI: {e}")
                    # Try to identify the issue
                    with open(contract["path"], 'r') as f:
                        content = f.read()
                        if content.strip().startswith('[') and content.strip().endswith(']'):
                            logger.info("File appears to be a JSON array, but has syntax errors")
                        elif content.strip().startswith('{') and content.strip().endswith('}'):
                            logger.info("File appears to be a JSON object, but has syntax errors")
                        else:
                            logger.info(f"File does not appear to be valid JSON. First 100 chars: {content[:100]}")
                except Exception as e:
                    logger.error(f"Failed to load ABI for {contract['name']}: {e}")
                
            # Set named ABI variables for backward compatibility
            self.BERRY_TEMP_AGENT_ABI = self.contract_abis.get("BerryTempAgent", [])
            self.BERRY_MANAGER_ABI = self.contract_abis.get("BerryManager", [])
            
            if self.contract_abis:
                logger.info(f"Successfully loaded contract ABIs: {', '.join(self.contract_abis.keys())}")
            else:
                logger.warning("No contract ABIs were successfully loaded")
            
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
           # Use higher default gas limits based on method
           if hasattr(contract_func, "__name__"):
               method_name = contract_func.__name__
               # Give processAgentRecommendation a higher gas limit due to known issues
               if "processAgentRecommendation" in method_name:
                   logger.info(f"Using high gas limit (500000) for {method_name} due to known issues")
                   return 500000
               elif "recordTemperature" in method_name:
                   logger.info(f"Using high gas limit (450000) for {method_name} due to known issues")
                   return 450000
               elif "create" in method_name.lower():
                   return 200000
               elif "process" in method_name.lower():
                   return 300000
               elif "complete" in method_name.lower():
                   return 400000
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
                # Check specifically for the arithmetic overflow/underflow error
                if "Panic error 0x11: Arithmetic operation" in str(e):
                    logger.warning(f"Arithmetic overflow/underflow detected: {e}, using high gas limit")
                    method_name = contract_func.__name__ if hasattr(contract_func, "__name__") else "unknown"
                    logger.info(f"Setting high gas limit (600000) for {method_name} due to arithmetic error")
                    estimated_gas = 600000
                else:
                    logger.warning(f"Gas estimation failed: {e}, using safe default")
                    # Use a safe default based on transaction type
                    method_name = contract_func.__name__ if hasattr(contract_func, "__name__") else "unknown"
                    
                    # Set default gas limits based on method
                    if "recordTemperature" in method_name:
                        estimated_gas = 450000  # Higher gas limit for recordTemperature
                    elif "create" in method_name.lower():
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
                
                # Special handling for processAgentRecommendation to prevent arithmetic errors
                if method == "processAgentRecommendation" and len(args) > 0:
                    batch_id = args[0]
                    # Check if batch has predictions before proceeding
                    try:
                        predictions = self.get_agent_predictions(batch_id)
                        if not predictions:
                            logger.warning(f"No predictions found for batch {batch_id}, skipping processAgentRecommendation")
                            return {
                                "success": False,
                                "error": "No predictions available for this batch",
                                "batch_id": batch_id
                            }
                    except Exception as e:
                        logger.warning(f"Could not check predictions: {e}")
                        # Continue with the transaction anyway, as it will be handled in the contract
                        
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
            
            # Use send_transaction method with increased gas limit
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "recordTemperature",
                "args": [batch_id, temperature, location],
                "gas_limit": 500000  
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