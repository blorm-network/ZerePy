from src.action_handler import list_registered_actions
import logging
import time
import os
import json
import requests
from dotenv import load_dotenv
from src.action_handler import register_action
from datetime import datetime, timedelta
import traceback
import asyncio

# Configure logging
logger = logging.getLogger("actions.sonic_actions")
file_handler = logging.FileHandler("berry_monitor.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
logger.addHandler(file_handler)

# Load environment variables
load_dotenv()

# Constants for berry temperature monitoring
BERRY_TEMP_AGENT_ADDRESS = "0x428bC2B646B3CfeD15699fBaf66688F928f80f56"
BERRY_MANAGER_ADDRESS = "0x70C0899d28Bf93D1cA1D36aE7f3c158Fecb6CAE9"
OPTIMAL_TEMP = 2   # 2°C
MAX_TEMP = 4       # 4°C
MIN_TEMP = 0       # 0°C

# Constants for alerting
ENABLE_ALERTS = os.getenv("ENABLE_ALERTS", "false").lower() == "true"
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
ALERT_WEBHOOK = os.getenv("ALERT_WEBHOOK", "")

# Health monitoring
health_stats = {
    "transaction_count": 0,
    "successful_transactions": 0,
    "failed_transactions": 0,
    "last_health_check": datetime.now(),
    "temperature_breaches": 0,
    "critical_breaches": 0,
    "warning_breaches": 0,
    "batches_created": 0,
    "batches_completed": 0
}

# Monitoring and alerting functions
def send_alert(alert_type, message, details=None):
    """Send an alert via configured channels"""
    if not ENABLE_ALERTS:
        logger.info(f"Alert would be sent (alerting disabled): {alert_type} - {message}")
        return
    
    alert_data = {
        "alert_type": alert_type,
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "details": details or {}
    }
    
    # Log alert
    logger.warning(f"ALERT: {alert_type} - {message}")
    
    # Send email alert if configured
    if ALERT_EMAIL:
        try:
            # Simplified email sending - in production, use a proper email library
            logger.info(f"Would send email alert to {ALERT_EMAIL}: {message}")
            # In a real implementation, you would add actual email sending code here
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    # Send webhook alert if configured
    if ALERT_WEBHOOK:
        try:
            requests.post(
                ALERT_WEBHOOK,
                json=alert_data,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")


def update_health_metrics(category, success=True, value=1):
    """Update health monitoring metrics"""
    global health_stats
    
    if category == "transaction":
        health_stats["transaction_count"] += value
        if success:
            health_stats["successful_transactions"] += value
        else:
            health_stats["failed_transactions"] += value
    
    elif category == "temperature_breach":
        # Increment the breach counter by 1, not by the dict value
        health_stats["temperature_breaches"] += 1  # Changed from: health_stats["temperature_breaches"] += value
        
        # Update breach severity counts
        severity = "unknown"
        if isinstance(value, dict) and "breach_severity" in value:
            severity = value["breach_severity"]
            
        if severity == "Critical":
            health_stats["critical_breaches"] += 1
        elif severity == "Warning":
            health_stats["warning_breaches"] += 1
    
    elif category == "batch_created":
        health_stats["batches_created"] += value
    
    elif category == "batch_completed":
        health_stats["batches_completed"] += value

def perform_health_check(agent):
    """Perform a system health check"""
    global health_stats
    
    try:
        logger.info("Performing system health check...")
        health_stats["last_health_check"] = datetime.now()
        
        # Check blockchain connection
        sonic_connection = agent.connection_manager.connections["sonic"]
        is_connected = sonic_connection._web3.is_connected() if not sonic_connection.use_mock_mode else True
        
        # Check account balance
        account_balance = 0
        if sonic_connection.account and not sonic_connection.use_mock_mode:
            account_balance = sonic_connection._web3.eth.get_balance(sonic_connection.account.address)
            account_balance_eth = sonic_connection._web3.from_wei(account_balance, 'ether')
            
            # Alert on low balance
            if account_balance_eth < 1:
                send_alert("low_balance", f"Account balance is low: {account_balance_eth} Sonic Tokens")
        
        # Check contract accessibility
        contract_accessible = False
        try:
            # Try a simple contract call to check accessibility
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "batchCount",
                "args": []
            }
            batch_count = sonic_connection.call_contract(tx_data)
            contract_accessible = True
        except Exception:
            contract_accessible = False
        
        # Calculate success rate
        success_rate = 0
        if health_stats["transaction_count"] > 0:
            success_rate = (health_stats["successful_transactions"] / health_stats["transaction_count"]) * 100
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "is_connected": is_connected,
            "contract_accessible": contract_accessible,
            "account_balance": str(account_balance),
            "transaction_count": health_stats["transaction_count"],
            "successful_transactions": health_stats["successful_transactions"],
            "failed_transactions": health_stats["failed_transactions"],
            "transaction_success_rate": f"{success_rate:.2f}%",
            "temperature_breaches": health_stats["temperature_breaches"],
            "critical_breaches": health_stats["critical_breaches"],
            "warning_breaches": health_stats["warning_breaches"],
            "batches_created": health_stats["batches_created"],
            "batches_completed": health_stats["batches_completed"]
        }
        
        # Alert on health issues
        if not is_connected:
            send_alert("connection_lost", "Blockchain connection is down", health_report)
        
        if not contract_accessible:
            send_alert("contract_inaccessible", "Smart contracts are not accessible", health_report)
        
        if success_rate < 80 and health_stats["transaction_count"] > 10:
            send_alert("low_success_rate", f"Transaction success rate is low: {success_rate:.2f}%", health_report)
        
        # Log health report
        logger.info(f"Health report: {json.dumps(health_report, indent=2)}")
        
        return health_report
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Berry Temperature Monitoring Actions
@register_action("monitor-berry-temperature")
async def monitor_berry_temperature(agent, **kwargs):
    """Monitor and analyze temperature data for berry shipments"""
    start_time = datetime.now()
    
    try:
        logger.info("Starting berry temperature monitoring...")
        
        # Get batch ID from parameters or use default
        batch_id = kwargs.get("batch_id", 0)
        temperature = kwargs.get("temperature")
        location = kwargs.get("location", "Unknown")
        batch_tag = f"[Batch #{batch_id}]"
        
        # Validate temperature data
        if temperature is None:
            # Use mock data if no temperature is provided
            mock_temps = [2.5, 3.1, 4.2, 5.0, 3.8, 2.9]
            temperature = mock_temps[int(datetime.now().timestamp()) % len(mock_temps)]
            logger.info(f"{batch_tag} Using mock temperature data: {temperature}°C")
            
        # Determine location from time of day if not provided
        if location == "Unknown":
            hour = datetime.now().hour
            if hour < 8:
                location = "Cold Storage"
            elif hour < 12:
                location = "Loading Dock"
            elif hour < 18:
                location = "Transport"
            else:
                location = "Delivery Center"
            logger.info(f"{batch_tag} Auto-determined location: {location}")
        
        logger.info(f"{batch_tag} Recording temperature {temperature}°C at {location}")
        
        # Call contract method to record temperature
        tx_data = {
            "contract_address": BERRY_TEMP_AGENT_ADDRESS,
            "method": "recordTemperature",
            "args": [batch_id, int(temperature * 10), location],
            "gas_limit": 500000
        }
        
        sonic_connection = agent.connection_manager.connections["sonic"]
        tx_result = sonic_connection.send_transaction(tx_data)
        
        # Update transaction metrics
        update_health_metrics("transaction", tx_result.get("success", False))
        
        logger.info(f"{batch_tag} Temperature recording transaction: {tx_result}")
        
        # Check for breaches
        is_breach = temperature > MAX_TEMP or temperature < MIN_TEMP
        breach_severity = "None"
        
        if is_breach:
            deviation = abs(temperature - OPTIMAL_TEMP)
            if deviation > 3:
                breach_severity = "Critical"
            elif deviation > 1:
                breach_severity = "Warning"
            else:
                breach_severity = "Minor"
            
            # Update breach metrics
           
            update_health_metrics("temperature_breach", True, {
                "batch_id": batch_id,
                "temperature": temperature,
                "breach_severity": breach_severity
            })
            
            # Send alerts for significant breaches
            if breach_severity in ["Critical", "Warning"]:
                send_alert(
                    f"temperature_breach_{breach_severity.lower()}", 
                    f"Temperature breach detected: {temperature}°C, Severity: {breach_severity}, Batch: {batch_id}, Location: {location}",
                    {
                        "batch_id": batch_id,
                        "temperature": temperature,
                        "location": location,
                        "severity": breach_severity,
                        "max_allowed": MAX_TEMP,
                        "min_allowed": MIN_TEMP,
                        "deviation": deviation,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
            logger.warning(f"{batch_tag} Temperature breach detected: {temperature}°C, Severity: {breach_severity}")
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"{batch_tag} Temperature monitoring completed in {execution_time:.2f} seconds")
            
        return {
            "status": "completed",
            "batch_id": batch_id,
            "temperature": temperature,
            "location": location,
            "is_breach": is_breach,
            "breach_severity": breach_severity,
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time
        }
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"Berry temperature monitoring failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Alert on action failure
        send_alert(
            "action_failure", 
            f"Temperature monitoring failed for batch {kwargs.get('batch_id', 0)}: {str(e)}",
            {
                "action": "monitor-berry-temperature",
                "batch_id": kwargs.get("batch_id", 0),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }
@register_action("manage-batch-sequence") 
async def manage_batch_sequence(agent, **kwargs):
    """Execute a complete batch lifecycle sequence"""
    start_time = datetime.now()
    
    try:
        logger.info("Starting batch sequence management...")
        
        # Get parameters
        berry_type = kwargs.get("berry_type", "Strawberry")
        temperatures = kwargs.get("temperatures", [2.0, 2.5, 3.0, 3.5, 2.8, 2.2])
        locations = kwargs.get("locations", ["Cold Storage", "Loading Dock", "Transport", "Transport", "Transport", "Delivery Center"])
        complete_shipment = kwargs.get("complete_shipment", False)
        
        # Step 1: Create a new batch
        logger.info(f"Step 1: Creating new batch for {berry_type}")
        create_result = await manage_batch_lifecycle(agent, action="create", berry_type=berry_type)
        
        if create_result.get("status") != "completed":
            raise Exception(f"Failed to create batch: {create_result.get('error', 'Unknown error')}")
        
        batch_id = create_result.get("batch_id", 0)
        batch_tag = f"[Batch #{batch_id}]"
        logger.info(f"{batch_tag} Successfully created new batch")
        
        # Step 2: Record multiple temperatures
        logger.info(f"{batch_tag} Step 2: Recording temperature sequence")
        
        temperature_results = []
        for i, (temp, location) in enumerate(zip(temperatures, locations)):
            logger.info(f"{batch_tag} Recording temperature {i+1}/{len(temperatures)}: {temp}°C at {location}")
            temp_result = await monitor_berry_temperature(agent, batch_id=batch_id, temperature=temp, location=location)
            
            if temp_result.get("status") != "completed":
                logger.warning(f"{batch_tag} Failed to record temperature {i+1}: {temp_result.get('error', 'Unknown error')}")
            else:
                temperature_results.append(temp_result)
            
            # Short delay between recordings
            await asyncio.sleep(1)
        
        # Step 3: Assess quality
        logger.info(f"{batch_tag} Step 3: Assessing quality")
        quality_result = await manage_berry_quality(agent, batch_id=batch_id)
        
        if quality_result.get("status") != "completed":
            raise Exception(f"Failed to assess quality: {quality_result.get('error', 'Unknown error')}")
        
        # Step 4: Process recommendations
        logger.info(f"{batch_tag} Step 4: Processing recommendations")
        rec_result = await process_agent_recommendations(agent, batch_id=batch_id)
        
        # Step 5: Complete shipment if requested
        if complete_shipment:
            logger.info(f"{batch_tag} Step 5: Completing shipment")
            complete_result = await manage_batch_lifecycle(agent, action="complete", batch_id=batch_id)
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"{batch_tag} Batch sequence completed in {execution_time:.2f} seconds")
        
        return {
            "status": "completed",
            "batch_id": batch_id,
            "berry_type": berry_type,
            "temperatures_recorded": len(temperature_results),
            "quality_details": quality_result,
            "shipment_completed": complete_shipment,
            "execution_time": execution_time
        }
        
    except Exception as e:
        logger.error(f"Batch sequence management failed: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e)
        }

@register_action("manage-berry-quality")
async def manage_berry_quality(agent, **kwargs):
    """Assess and predict berry quality based on temperature history"""
    start_time = datetime.now()
    
    try:
        logger.info("Starting berry quality assessment...")
        
        # Get batch ID from parameters or use default
        batch_id = kwargs.get("batch_id", 0)
        batch_tag = f"[Batch #{batch_id}]"
        
        # Get temperature history for the batch
        tx_data = {
            "contract_address": BERRY_TEMP_AGENT_ADDRESS,
            "method": "getTemperatureHistory",
            "args": [batch_id]
        }
        
        sonic_connection = agent.connection_manager.connections["sonic"]
        temp_history = sonic_connection.call_contract(tx_data)
        
        # If no history available, use mock data
        if not temp_history or len(temp_history) == 0:
            logger.info(f"{batch_tag} No temperature history found, using mock data")
            
            # Generate mock temperature history
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
                    "timestamp": (base_time + timedelta(hours=i*2)).isoformat(),
                    "temperature": temp,
                    "location": locations[i],
                    "isBreached": temp > MAX_TEMP or temp < MIN_TEMP
                })
            
            temp_history = mock_history
        
        # Calculate quality impact
        quality_score = 100
        shelf_life_hours = 72  # Default 3-day shelf life for berries
        
        # Get batch details to determine berry type
        batch_details_tx_data = {
            "contract_address": BERRY_TEMP_AGENT_ADDRESS,
            "method": "getBatchDetails",
            "args": [batch_id]
        }
        
        batch_details = sonic_connection.call_contract(batch_details_tx_data)
        berry_type = "Strawberry"  # Default
        
        if batch_details and len(batch_details) > 1:
            berry_type = batch_details[1]
            logger.info(f"{batch_tag} Berry type: {berry_type}")
        
        # Adjust base shelf life based on berry type
        berry_shelf_life = {
            "Strawberry": 72,
            "Blueberry": 96,
            "Raspberry": 48,
            "Blackberry": 48
        }
        
        shelf_life_hours = berry_shelf_life.get(berry_type, 72)
        logger.info(f"{batch_tag} Base shelf life for {berry_type}: {shelf_life_hours} hours")
        
        # Process temperature readings
        reading_count = 0
        breach_count = 0
        cumulative_breach_severity = 0
        
        for reading in temp_history:
            reading_count += 1
            
            # Handle both dict and list formats
            if isinstance(reading, dict):
                temp = reading.get("temperature", 0)
                timestamp = reading.get("timestamp", "")
                location = reading.get("location", "Unknown")
            else:  # Assume list format from contract
                temp = reading[1] / 10.0  # Contract stores temp * 10
                timestamp = datetime.fromtimestamp(reading[0]).isoformat() if reading[0] else ""
                location = reading[2] if len(reading) > 2 else "Unknown"
                
            if isinstance(temp, str):
                temp = float(temp)
            
            logger.debug(f"{batch_tag} Processing reading: {temp}°C at {location} - {timestamp}")
                
            if temp > MAX_TEMP:
                breach_count += 1
                deviation = temp - MAX_TEMP
                quality_score -= deviation * 5
                shelf_life_hours -= deviation * 4
                cumulative_breach_severity += deviation
                logger.debug(f"{batch_tag} High temperature breach: {temp}°C, impact: -{deviation * 5} quality points")
            elif temp < MIN_TEMP:
                breach_count += 1
                deviation = MIN_TEMP - temp
                quality_score -= deviation * 7
                shelf_life_hours -= deviation * 6
                cumulative_breach_severity += deviation
                logger.debug(f"{batch_tag} Low temperature breach: {temp}°C, impact: -{deviation * 7} quality points")
        
        # Ensure we don't go below zero
        quality_score = max(0, quality_score)
        shelf_life_hours = max(0, shelf_life_hours)
        
        # Record breach statistics
        breach_percentage = (breach_count / reading_count * 100) if reading_count > 0 else 0
        logger.info(f"{batch_tag} Temperature breach statistics: {breach_count}/{reading_count} readings ({breach_percentage:.1f}%)")
        
        # Determine recommended action based on quality
        action = "No Action"
        action_description = "Quality is within acceptable parameters."
        
        if quality_score < 60:
            action = "Reject"
            action_description = "Quality severely compromised. Recommend rejection."
        elif quality_score < 70:
            action = "Reroute"
            action_description = "Quality concerns detected. Recommend rerouting to nearest facility."
        elif quality_score < 80:
            action = "Expedite"
            action_description = "Quality at risk. Recommend expedited delivery."
        elif quality_score < 90:
            action = "Alert"
            action_description = "Minor quality impact. Continue monitoring closely."
        
        # Alert on severe quality impact
        if quality_score < 70:
            send_alert(
                "quality_alert", 
                f"Low quality score detected: {quality_score:.1f}/100 for batch {batch_id} ({berry_type}). Action: {action}",
                {
                    "batch_id": batch_id,
                    "berry_type": berry_type,
                    "quality_score": quality_score,
                    "shelf_life_hours": shelf_life_hours,
                    "readings": reading_count,
                    "breaches": breach_count,
                    "recommended_action": action,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"{batch_tag} Quality assessment complete: {action}, Score: {quality_score:.1f}/100, Shelf life: {shelf_life_hours:.1f} hours")
        
        result = {
            "status": "completed",
            "batch_id": batch_id,
            "berry_type": berry_type,
            "quality_score": round(quality_score, 1),
            "shelf_life_hours": round(shelf_life_hours, 1),
            "temperature_readings": reading_count,
            "breach_count": breach_count,
            "breach_percentage": round(breach_percentage, 1),
            "recommended_action": action,
            "action_description": action_description,
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time
        }
        
        return result
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"Berry quality management failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Alert on action failure
        send_alert(
            "action_failure", 
            f"Quality assessment failed for batch {kwargs.get('batch_id', 0)}: {str(e)}",
            {
                "action": "manage-berry-quality",
                "batch_id": kwargs.get("batch_id", 0),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }

@register_action("process-agent-recommendations")
async def process_agent_recommendations(agent, **kwargs):
    """Process agent recommendations and update supplier reputation"""
    start_time = datetime.now()
    
    try:
        logger.info("Processing agent recommendations...")
        
        # Get parameters
        batch_id = kwargs.get("batch_id", 0)
        quality_score = kwargs.get("quality_score")
        recommended_action = kwargs.get("recommended_action")
        batch_tag = f"[Batch #{batch_id}]"
        
        # If quality score not provided, fetch from previous action
        if quality_score is None:
            logger.info(f"{batch_tag} Quality score not provided, fetching from quality management")
            # Call the quality management function
            quality_result = await manage_berry_quality(agent, batch_id=batch_id)
            quality_score = quality_result.get("quality_score", 80)
            recommended_action = quality_result.get("recommended_action", "No Action")
            logger.info(f"{batch_tag} Fetched quality score: {quality_score}, action: {recommended_action}")
        
        # Call contract method to process recommendation
        tx_data = {
            "contract_address": BERRY_MANAGER_ADDRESS,
            "method": "processAgentRecommendation",
            "args": [batch_id],
            "gas_limit": 500000  # Increased gas limit
        }
        
        sonic_connection = agent.connection_manager.connections["sonic"]
        tx_result = sonic_connection.send_transaction(tx_data)
        
        # Update transaction metrics
        update_health_metrics("transaction", tx_result.get("success", False))
        
        logger.info(f"{batch_tag} Recommendation processing transaction: {tx_result}")
        
        # Get supplier details
        supplier_tx_data = {
            "contract_address": BERRY_MANAGER_ADDRESS,
            "method": "getSupplierDetails",
            "args": [sonic_connection.account.address]
        }
        
        supplier_details = sonic_connection.call_contract(supplier_tx_data)
        
        # If no details available, use mock data
        if not supplier_details:
            supplier_details_dict = {
                "reputation": 85,
                "totalBatches": 12,
                "successfulBatches": 10
            }
        else:
            # Convert list or tuple to dict if needed
            if isinstance(supplier_details, (list, tuple)):
                supplier_details_dict = {
                    "account": supplier_details[0],
                    "isRegistered": supplier_details[1],
                    "reputation": supplier_details[2],
                    "totalBatches": supplier_details[3],
                    "successfulBatches": supplier_details[4],
                    "lastActionTime": supplier_details[5]
                }
            else:
                supplier_details_dict = supplier_details  # If it's already a dict
        
        # Calculate supplier action based on quality
        supplier_action = "None"
        
        if quality_score >= 90:
            supplier_action = "Reward"
        elif quality_score < 60:
            supplier_action = "Warn"
        
        # Alert on supplier issues
        if supplier_action == "Warn":
            supplier_name = "Unknown"
            if "account" in supplier_details_dict:
                supplier_name = supplier_details_dict["account"]
            
            send_alert(
                "supplier_warning", 
                f"Supplier warning issued for batch {batch_id} due to low quality score: {quality_score:.1f}/100",
                {
                    "batch_id": batch_id,
                    "supplier": supplier_name,
                    "quality_score": quality_score,
                    "recommended_action": recommended_action,
                    "supplier_reputation": supplier_details_dict.get("reputation", 0),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"{batch_tag} Recommendation processing complete in {execution_time:.2f} seconds")
        
        return {
            "status": "completed",
            "batch_id": batch_id,
            "quality_score": quality_score,
            "recommended_action": recommended_action,
            "supplier_reputation": supplier_details_dict.get("reputation", 85),
            "total_batches": supplier_details_dict.get("totalBatches", 12),
            "successful_batches": supplier_details_dict.get("successfulBatches", 10),
            "supplier_action": supplier_action,
            "timestamp": datetime.now().isoformat(),
            "transaction_hash": tx_result.get("transaction_hash", ""),
            "transaction_url": tx_result.get("transaction_url", ""),
            "execution_time": execution_time
        }
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"Process agent recommendations failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Alert on action failure
        send_alert(
            "action_failure", 
            f"Recommendation processing failed for batch {kwargs.get('batch_id', 0)}: {str(e)}",
            {
                "action": "process-agent-recommendations",
                "batch_id": kwargs.get("batch_id", 0),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }

@register_action("manage-batch-lifecycle")
async def manage_batch_lifecycle(agent, **kwargs):
    """Manage berry batch lifecycle from creation to delivery"""
    start_time = datetime.now()
    
    try:
        logger.info("Managing batch lifecycle...")
        
        # Get parameters
        action = kwargs.get("action", "create")
        berry_type = kwargs.get("berry_type", "Strawberry")
        batch_id = kwargs.get("batch_id", 0)
        
        # Get Sonic connection
        sonic_connection = agent.connection_manager.connections["sonic"]
        
        if action == "create":
            # Create a new batch
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "createBatch",
                "args": [berry_type],
                "gas_limit": 300000  # Increased gas limit
            }
            
            tx_result = sonic_connection.send_transaction(tx_data)
            
            # Update transaction metrics
            update_health_metrics("transaction", tx_result.get("success", False))
            
            logger.info(f"Batch creation transaction: {tx_result}")
            
            # Get the batch count to determine the new batch ID
            count_tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "batchCount",
                "args": []
            }
            
            batch_count = sonic_connection.call_contract(count_tx_data)
            if batch_count:
                batch_id = int(batch_count) - 1
            
            # Update batch created metrics
            update_health_metrics("batch_created")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Created new batch #{batch_id} ({berry_type}) in {execution_time:.2f} seconds")
                
            return {
                "status": "completed",
                "action": "create",
                "berry_type": berry_type,
                "batch_id": batch_id,
                "timestamp": datetime.now().isoformat(),
                "transaction_hash": tx_result.get("transaction_hash", ""),
                "transaction_url": tx_result.get("transaction_url", ""),
                "execution_time": execution_time
            }
            
        
        elif action == "complete":
            batch_tag = f"[Batch #{batch_id}]"
            logger.info(f"{batch_tag} Shipment completion is now handled via frontend")
    
    # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
    
            return {
                 "status": "redirected",
                 "action": "complete",
                 "batch_id": batch_id,
                 "message": "Shipment completion is now handled directly through the frontend interface",
                 "timestamp": datetime.now().isoformat(),
                 "execution_time": execution_time
    }
        
        elif action == "status":
            batch_tag = f"[Batch #{batch_id}]"
            
            # Get batch details
            tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getBatchDetails",
                "args": [batch_id]
            }
            
            batch_details = sonic_connection.call_contract(tx_data)
            
         # If no details available, use mock data
            if not batch_details:
                batch_details_dict = {
                    "batchId": batch_id,
                    "berryType": berry_type,
                    "startTime": int((datetime.now() - timedelta(hours=24)).timestamp()),
                    "status": 1,  # 1 = InTransit
                    "qualityScore": 85,
                    "predictedShelfLife": 60 * 60 * 60  # 60 hours in seconds
                }
            else:
                # Convert list or tuple to dict if needed
                if isinstance(batch_details, (list, tuple)):
                    batch_details_dict = {
                        "batchId": batch_details[0],
                        "berryType": batch_details[1],
                        "startTime": batch_details[2],
                        "endTime": batch_details[3],
                        "isActive": batch_details[4],
                        "status": batch_details[5],
                        "qualityScore": batch_details[6],
                        "predictedShelfLife": batch_details[7]
                    }
                else:
                    batch_details_dict = batch_details  # If it's already a dict
            
            status_map = {
                0: "Created",
                1: "InTransit",
                2: "Delivered",
                3: "Rejected"
            }
            
            current_status = status_map.get(batch_details_dict.get("status", 1), "InTransit")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"{batch_tag} Retrieved batch status: {current_status} in {execution_time:.2f} seconds")
            
            return {
                "status": "completed",
                "action": "status",
                "batch_id": batch_id,
                "berry_type": batch_details_dict.get("berryType", berry_type),
                "batch_status": current_status,
                "quality_score": batch_details_dict.get("qualityScore", 85),
                "predicted_shelf_life_hours": batch_details_dict.get("predictedShelfLife", 60 * 60 * 60) / 3600,
                "timestamp": datetime.now().isoformat(),
                "execution_time": execution_time
            }
            
        elif action == "report":
            batch_tag = f"[Batch #{batch_id}]"
            logger.info(f"{batch_tag} Generating comprehensive batch report")
            
            # Get batch details
            batch_tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getBatchDetails",
                "args": [batch_id]
            }
            batch_details = sonic_connection.call_contract(batch_tx_data)
            
            # Get temperature history
            temp_tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getTemperatureHistory",
                "args": [batch_id]
            }
            temp_history = sonic_connection.call_contract(temp_tx_data)
            
            # Get agent predictions
            pred_tx_data = {
                "contract_address": BERRY_TEMP_AGENT_ADDRESS,
                "method": "getAgentPredictions",
                "args": [batch_id]
            }
            predictions = sonic_connection.call_contract(pred_tx_data)
            
            # Format the batch details
            if not batch_details:
                batch_details_dict = {
                    "batchId": batch_id,
                    "berryType": berry_type,
                    "startTime": int((datetime.now() - timedelta(hours=24)).timestamp()),
                    "endTime": 0,
                    "isActive": True,
                    "status": 1,  # 1 = InTransit
                    "qualityScore": 85,
                    "predictedShelfLife": 60 * 60 * 60  # 60 hours in seconds
                }
            else:
                # Convert list or tuple to dict if needed
                if isinstance(batch_details, (list, tuple)):
                    batch_details_dict = {
                        "batchId": batch_details[0],
                        "berryType": batch_details[1],
                        "startTime": batch_details[2],
                        "endTime": batch_details[3],
                        "isActive": batch_details[4],
                        "status": batch_details[5],
                        "qualityScore": batch_details[6],
                        "predictedShelfLife": batch_details[7]
                    }
                else:
                    batch_details_dict = batch_details  # If it's already a dict
            
            # Format the temperature history
            formatted_history = []
            breach_count = 0
            max_temp = 0
            min_temp = 100  # Initialize to high value
            
            for reading in temp_history or []:
                if isinstance(reading, dict):
                    formatted_reading = reading
                else:  # Assume list format from contract
                    temp = reading[1] / 10.0 if len(reading) > 1 else 0
                    formatted_reading = {
                        "timestamp": reading[0] if len(reading) > 0 else 0,
                        "temperature": temp,
                        "location": reading[2] if len(reading) > 2 else "Unknown",
                        "isBreached": reading[3] if len(reading) > 3 else False
                    }
                
                # Update statistics
                temp = formatted_reading.get("temperature", 0)
                max_temp = max(max_temp, temp)
                min_temp = min(min_temp, temp)
                
                if formatted_reading.get("isBreached", False):
                    breach_count += 1
                
                formatted_history.append(formatted_reading)
            
            # Format the predictions
            formatted_predictions = []
            for prediction in predictions or []:
                if isinstance(prediction, dict):
                    formatted_prediction = prediction
                else:  # Assume list format from contract
                    formatted_prediction = {
                        "timestamp": prediction[0] if len(prediction) > 0 else 0,
                        "predictedQuality": prediction[1] if len(prediction) > 1 else 0,
                        "recommendedAction": prediction[2] if len(prediction) > 2 else 0,
                        "actionDescription": prediction[3] if len(prediction) > 3 else ""
                    }
                
                formatted_predictions.append(formatted_prediction)
            
            # Status mapping
            status_map = {
                0: "Created",
                1: "InTransit",
                2: "Delivered",
                3: "Rejected"
            }
            
            # Build detailed report
            start_time_str = datetime.fromtimestamp(batch_details_dict.get("startTime", 0)).isoformat() if batch_details_dict.get("startTime", 0) else "Unknown"
            end_time_str = datetime.fromtimestamp(batch_details_dict.get("endTime", 0)).isoformat() if batch_details_dict.get("endTime", 0) and batch_details_dict.get("endTime", 0) != 0 else "In Progress"
            
            status_int = batch_details_dict.get("status", 1)
            status_str = status_map.get(status_int, "Unknown")
            
            shelf_life_hours = batch_details_dict.get("predictedShelfLife", 0) / 3600
            
            reading_count = len(formatted_history)
            breach_percentage = (breach_count / reading_count * 100) if reading_count > 0 else 0
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"{batch_tag} Generated complete batch report in {execution_time:.2f} seconds")
            
            return {
                "status": "completed",
                "action": "report",
                "batch_id": batch_id,
                "batch_details": {
                    "berry_type": batch_details_dict.get("berryType", "Unknown"),
                    "status": status_str,
                    "quality_score": batch_details_dict.get("qualityScore", 0),
                    "shelf_life_hours": shelf_life_hours,
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "is_active": batch_details_dict.get("isActive", False)
                },
                "temperature_stats": {
                    "reading_count": reading_count,
                    "breach_count": breach_count,
                    "breach_percentage": f"{breach_percentage:.1f}%",
                    "max_temperature": max_temp,
                    "min_temperature": min_temp,
                    "readings": formatted_history[:5]  # Include first 5 readings for brevity
                },
                "predictions": formatted_predictions,
                "timestamp": datetime.now().isoformat(),
                "execution_time": execution_time
            }
        
        else:
            raise ValueError(f"Unknown action: {action}")
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"Batch lifecycle management failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Alert on action failure
        send_alert(
            "action_failure", 
            f"Batch lifecycle management failed for action {kwargs.get('action', 'unknown')}, batch {kwargs.get('batch_id', 0)}: {str(e)}",
            {
                "action": "manage-batch-lifecycle",
                "sub_action": kwargs.get("action", "unknown"),
                "batch_id": kwargs.get("batch_id", 0),
                "berry_type": kwargs.get("berry_type", ""),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }

@register_action("system-health-check")
async def system_health_check(agent, **kwargs):
    """Perform a system health check and return metrics"""
    start_time = datetime.now()
    
    try:
        logger.info("Starting system health check...")
        
        # Perform health check
        health_report = perform_health_check(agent)
        
        # Reset error counters if requested
        reset_counters = kwargs.get("reset_counters", False)
        if reset_counters:
            logger.info("Resetting health metrics counters")
            health_stats["transaction_count"] = 0
            health_stats["successful_transactions"] = 0
            health_stats["failed_transactions"] = 0
            health_stats["temperature_breaches"] = 0
            health_stats["critical_breaches"] = 0
            health_stats["warning_breaches"] = 0
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Health check completed in {execution_time:.2f} seconds")
        
        return {
            "status": "completed",
            "health_report": health_report,
            "counters_reset": reset_counters,
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time
        }
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"System health check failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }

@register_action("manage-batch-sequence")
async def manage_batch_sequence(agent, **kwargs):
    """Execute a complete batch lifecycle sequence"""
    start_time = datetime.now()
    
    try:
        logger.info("Starting batch sequence management...")
        
        # Get parameters
        berry_type = kwargs.get("berry_type", "Strawberry")
        temperatures = kwargs.get("temperatures", [2.0, 2.5, 3.0, 3.5, 2.8, 2.2])
        locations = kwargs.get("locations", ["Cold Storage", "Loading Dock", "Transport", "Transport", "Transport", "Delivery Center"])
        complete_shipment = kwargs.get("complete_shipment", False)
        
        # Step 1: Create a new batch
        logger.info(f"Step 1: Creating new batch for {berry_type}")
        create_result = await manage_batch_lifecycle(agent, action="create", berry_type=berry_type)
        
        if create_result.get("status") != "completed":
            raise Exception(f"Failed to create batch: {create_result.get('error', 'Unknown error')}")
        
        batch_id = create_result.get("batch_id", 0)
        batch_tag = f"[Batch #{batch_id}]"
        logger.info(f"{batch_tag} Successfully created new batch")
        
        # Step 2: Record multiple temperatures
        logger.info(f"{batch_tag} Step 2: Recording temperature sequence")
        
        temperature_results = []
        for i, (temp, location) in enumerate(zip(temperatures, locations)):
            logger.info(f"{batch_tag} Recording temperature {i+1}/{len(temperatures)}: {temp}°C at {location}")
            temp_result = await monitor_berry_temperature(agent, batch_id=batch_id, temperature=temp, location=location)
            
            if temp_result.get("status") != "completed":
                logger.warning(f"{batch_tag} Failed to record temperature {i+1}: {temp_result.get('error', 'Unknown error')}")
            else:
                temperature_results.append(temp_result)
            
            # Brief delay to avoid transaction collisions
            await asyncio.sleep(1)
        
        # Step 3: Assess quality
        logger.info(f"{batch_tag} Step 3: Assessing quality")
        quality_result = await manage_berry_quality(agent, batch_id=batch_id)
        
        if quality_result.get("status") != "completed":
            raise Exception(f"Failed to assess quality: {quality_result.get('error', 'Unknown error')}")
        
        quality_score = quality_result.get("quality_score", 0)
        shelf_life = quality_result.get("shelf_life_hours", 0)
        recommended_action = quality_result.get("recommended_action", "Unknown")
        
        logger.info(f"{batch_tag} Quality assessment complete: Score {quality_score}/100, Shelf life: {shelf_life} hours, Action: {recommended_action}")
        
        # Step 4: Process recommendations
        logger.info(f"{batch_tag} Step 4: Processing recommendations")
        rec_result = await process_agent_recommendations(
            agent, 
            batch_id=batch_id, 
            quality_score=quality_score,
            recommended_action=recommended_action
        )
        
        if rec_result.get("status") != "completed":
            raise Exception(f"Failed to process recommendations: {rec_result.get('error', 'Unknown error')}")
        
        logger.info(f"{batch_tag} Recommendation processing complete")
        
        manual_completion_message = None
        report_result = {"batch_details": {}}  # Define report_result with a default value
        
        if complete_shipment:
            logger.info(f"{batch_tag} Step 5: Shipment must be completed via frontend")
            manual_completion_message = "Shipment completion is now handled directly through the frontend interface"
            logger.info(f"{batch_tag} Please complete shipment using the frontend interface")
        else:
            logger.info(f"{batch_tag} Skipping shipment completion as per request")

# Then later in the return statement, include it:
        return {
            "status": "completed",
            "batch_id": batch_id,
            "berry_type": berry_type,
            "temperatures_recorded": len(temperature_results),
            "quality_score": quality_score,
            "shelf_life_hours": shelf_life,
            "recommended_action": recommended_action,
            "shipment_completed": complete_shipment,
            "manual_completion_message": manual_completion_message,  # Include the message here
            "report": report_result.get("batch_details", {}),
            "timestamp": datetime.now().isoformat(),
            "execution_time": execution_time
        }
        
        
    except Exception as e:
        # Log detailed error with traceback
        logger.error(f"Batch sequence management failed: {str(e)}", exc_info=True)
        
        # Calculate execution time even for failures
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Alert on action failure
        send_alert(
            "action_failure", 
            f"Batch sequence management failed: {str(e)}",
            {
                "action": "manage-batch-sequence",
                "berry_type": kwargs.get("berry_type", ""),
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": execution_time
            }
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "execution_time": execution_time
        }

# Helper function to verify action registration
def verify_action_registration():
    """Verify that all required actions are registered"""
    from src.action_handler import list_registered_actions
    actions = list_registered_actions()
    logger.info(f"Registered berry actions: {actions}")
    required_actions = [
        "monitor-berry-temperature", 
        "manage-berry-quality", 
        "process-agent-recommendations", 
        "manage-batch-lifecycle",
        "system-health-check",
        "manage-batch-sequence"
    ]
    missing = [a for a in required_actions if a not in actions]
    if missing:
        logger.warning(f"Missing actions: {missing}")
    return len(missing) == 0

# Run verification
verify_action_registration()