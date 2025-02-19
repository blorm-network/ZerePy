# src/actions/sonic_actions.py
import logging
from dotenv import load_dotenv
from src.action_handler import register_action
from datetime import datetime, timedelta
import json

logger = logging.getLogger("actions.sonic_actions")

# Core Smart Contract Actions
@register_action("initialize-smart-contract")
def initialize_smart_contract(agent, **kwargs):
    """Initialize supply chain smart contract on Sonic blockchain"""
    try:
        contract_params = {
            "owner_address": kwargs.get("owner_address"),
            "token_address": kwargs.get("token_address"),
            "min_stake": float(kwargs.get("min_stake", 1000))
        }
        return agent.connection_manager.connections["sonic"].deploy_contract(
            contract_params=contract_params
        )
    except Exception as e:
        logger.error(f"Failed to initialize smart contract: {str(e)}")
        return None

@register_action("register-supply-chain-participant")
def register_participant(agent, **kwargs):
    """Register a new participant in the supply chain"""
    try:
        participant_data = {
            "address": kwargs.get("address"),
            "role": kwargs.get("role"),
            "stake_amount": float(kwargs.get("stake_amount")),
            "metadata": kwargs.get("metadata", {})
        }
        return agent.connection_manager.connections["sonic"].register_participant(
            participant_data=participant_data
        )
    except Exception as e:
        logger.error(f"Failed to register participant: {str(e)}")
        return None

# Temperature Monitoring Actions
@register_action("monitor-temperature")
def monitor_temperature(agent, **kwargs):
    """Monitor and analyze temperature data from IoT sensors"""
    try:
        # Get current temperature readings
        readings = agent.connection_manager.connections["sonic"].get_temperature_readings()
        
        # Analyze for breaches
        breaches = []
        for reading in readings:
            if is_temperature_breach(reading):
                breach_data = {
                    "shipment_id": reading["shipment_id"],
                    "temperature": reading["temperature"],
                    "duration": calculate_breach_duration(reading),
                    "severity": calculate_breach_severity(reading),
                    "timestamp": datetime.now().isoformat()
                }
                breaches.append(breach_data)
                
                # Record breach on blockchain
                agent.connection_manager.connections["sonic"].record_temperature_breach(breach_data)
                
                # Trigger corrective actions
                if breach_data["severity"] == "critical":
                    initiate_emergency_protocol(agent, breach_data)
                else:
                    initiate_corrective_actions(agent, breach_data)
        
        return {
            "status": "completed",
            "breaches": breaches,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Temperature monitoring failed: {str(e)}")
        return None

# Demand Prediction Actions
@register_action("predict-demand")
def predict_demand(agent, **kwargs):
    """Generate demand forecasts using historical data and current factors"""
    try:
        # Collect prediction inputs
        historical_data = agent.connection_manager.connections["sonic"].get_historical_data(days=90)
        seasonal_factors = get_seasonal_factors()
        weather_data = get_weather_data()
        local_events = get_local_events()
        
        # Generate prediction
        prediction = {
            "forecast": calculate_demand_forecast(
                historical_data,
                seasonal_factors,
                weather_data,
                local_events
            ),
            "confidence_interval": calculate_confidence_interval(historical_data),
            "factors": {
                "seasonal": seasonal_factors,
                "weather": weather_data,
                "events": local_events
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Record prediction on blockchain
        agent.connection_manager.connections["sonic"].record_demand_prediction(prediction)
        
        return prediction
    except Exception as e:
        logger.error(f"Demand prediction failed: {str(e)}")
        return None

# Route Optimization Actions
@register_action("optimize-routes")
def optimize_routes(agent, **kwargs):
    """Optimize delivery routes considering multiple constraints"""
    try:
        # Get current delivery requirements
        deliveries = agent.connection_manager.connections["sonic"].get_pending_deliveries()
        current_conditions = {
            "traffic": get_traffic_data(),
            "weather": get_weather_data(),
            "vehicle_status": get_vehicle_status(),
            "temperature_zones": get_temperature_zones()
        }
        
        # Generate optimized routes
        optimized_routes = calculate_optimal_routes(
            deliveries=deliveries,
            conditions=current_conditions,
            constraints={
                "max_duration": 480,  # 8 hours
                "temperature_variance": 1.5,
                "priority_weight": 3
            }
        )
        
        # Record routes on blockchain
        route_data = {
            "routes": optimized_routes,
            "conditions": current_conditions,
            "metrics": calculate_route_metrics(optimized_routes),
            "timestamp": datetime.now().isoformat()
        }
        agent.connection_manager.connections["sonic"].record_route_plan(route_data)
        
        return route_data
    except Exception as e:
        logger.error(f"Route optimization failed: {str(e)}")
        return None

# Shelf Life Management Actions
@register_action("manage-shelf-life")
def manage_shelf_life(agent, **kwargs):
    """Track and predict product shelf life"""
    try:
        # Get current inventory status
        inventory = agent.connection_manager.connections["sonic"].get_current_inventory()
        
        # Process each inventory item
        shelf_life_data = {}
        for item in inventory:
            shelf_life_data[item["id"]] = {
                "remaining_life": calculate_remaining_shelf_life(
                    base_life=item["base_shelf_life"],
                    temperature_history=item["temperature_history"],
                    handling_events=item["handling_events"]
                ),
                "quality_score": calculate_quality_score(item),
                "storage_recommendations": generate_storage_recommendations(item),
                "priority_level": calculate_distribution_priority(item)
            }
        
        # Update blockchain records
        agent.connection_manager.connections["sonic"].update_shelf_life_data({
            "shelf_life": shelf_life_data,
            "timestamp": datetime.now().isoformat()
        })
        
        return shelf_life_data
    except Exception as e:
        logger.error(f"Shelf life management failed: {str(e)}")
        return None

# Contract Execution Actions
@register_action("execute-contracts")
def execute_contracts(agent, **kwargs):
    """Manage smart contracts on Sonic blockchain"""
    try:
        # Get pending contract actions
        pending_actions = agent.connection_manager.connections["sonic"].get_pending_contract_actions()
        
        results = []
        for action in pending_actions:
            result = None
            if action["type"] == "create_shipment":
                result = create_shipment_contract(agent, action["data"])
            elif action["type"] == "update_status":
                result = update_shipment_status(agent, action["data"])
            elif action["type"] == "complete_shipment":
                result = complete_shipment(agent, action["data"])
            elif action["type"] == "process_payment":
                result = process_payment(agent, action["data"])
            elif action["type"] == "handle_dispute":
                result = handle_dispute(agent, action["data"])
            
            if result:
                results.append({
                    "action": action["type"],
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })
        
        return results
    except Exception as e:
        logger.error(f"Contract execution failed: {str(e)}")
        return None

# Helper Functions
def is_temperature_breach(reading):
    """Check if temperature reading constitutes a breach"""
    return (reading["temperature"] > reading["max_threshold"] or 
            reading["temperature"] < reading["min_threshold"])

def calculate_breach_duration(reading):
    """Calculate duration of temperature breach"""
    if "breach_start" not in reading:
        return 0
    start_time = datetime.fromisoformat(reading["breach_start"])
    return (datetime.now() - start_time).total_seconds()

def calculate_breach_severity(reading):
    """Calculate severity of temperature breach"""
    deviation = abs(reading["temperature"] - reading["target_temperature"])
    duration = calculate_breach_duration(reading)
    
    if deviation > 5 or duration > 3600:  # 1 hour
        return "critical"
    elif deviation > 2 or duration > 1800:  # 30 minutes
        return "warning"
    return "minor"

def initiate_emergency_protocol(agent, breach_data):
    """Handle critical temperature breaches"""
    # Notify stakeholders
    notify_stakeholders(agent, breach_data)
    # Adjust route if possible
    adjust_route(agent, breach_data["shipment_id"])
    # Update smart contract
    update_shipment_status(agent, {
        "shipment_id": breach_data["shipment_id"],
        "status": "emergency",
        "breach_data": breach_data
    })

def calculate_demand_forecast(historical_data, seasonal_factors, weather_data, events):
    """Calculate demand forecast based on multiple factors"""
    base_demand = calculate_base_demand(historical_data)
    seasonal_adjustment = calculate_seasonal_adjustment(seasonal_factors)
    weather_adjustment = calculate_weather_adjustment(weather_data)
    event_adjustment = calculate_event_adjustment(events)
    
    return base_demand * seasonal_adjustment * weather_adjustment * event_adjustment

def calculate_optimal_routes(deliveries, conditions, constraints):
    """Calculate optimal delivery routes"""
    # Implementation would include routing algorithm
    # Consider temperature zones, time windows, and other constraints
    return []

def calculate_remaining_shelf_life(base_life, temperature_history, handling_events):
    """Calculate remaining shelf life for a product"""
    # Implementation would include shelf life calculation algorithm
    return 0

def create_shipment_contract(agent, data):
    """Create a new shipment smart contract"""
    try:
        return agent.connection_manager.connections["sonic"].create_shipment(data)
    except Exception as e:
        logger.error(f"Failed to create shipment contract: {str(e)}")
        return None

def process_payment(agent, data):
    """Process payment for completed shipment"""
    try:
        return agent.connection_manager.connections["sonic"].process_payment(data)
    except Exception as e:
        logger.error(f"Failed to process payment: {str(e)}")
        return None

def handle_dispute(agent, data):
    """Handle dispute in shipment contract"""
    try:
        return agent.connection_manager.connections["sonic"].handle_dispute(data)
    except Exception as e:
        logger.error(f"Failed to handle dispute: {str(e)}")
        return None