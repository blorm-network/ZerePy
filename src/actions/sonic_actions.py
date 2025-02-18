# src/actions/supply_chain_sonic_actions.py
import logging
from dotenv import load_dotenv
from src.action_handler import register_action

logger = logging.getLogger("actions.supply_chain_sonic")

@register_action("initialize-smart-contract")
def initialize_smart_contract(agent, **kwargs):
    """Initialize supply chain smart contract on Sonic blockchain
    """
    try:
        # Get contract parameters
        contract_params = {
            "owner_address": kwargs.get("owner_address"),
            "token_address": kwargs.get("token_address"),  # For payment token
            "min_stake": float(kwargs.get("min_stake", 100))  # Minimum stake for participants
        }
        
        # Deploy or connect to existing contract
        return agent.connection_manager.connections["sonic"].deploy_contract(
            contract_params=contract_params
        )

    except Exception as e:
        logger.error(f"Failed to initialize smart contract: {str(e)}")
        return None

@register_action("register-supply-chain-participant")
def register_participant(agent, **kwargs):
    """Register a new participant in the supply chain
    """
    try:
        participant_data = {
            "address": kwargs.get("address"),
            "role": kwargs.get("role"),  # supplier, distributor, retailer
            "stake_amount": float(kwargs.get("stake_amount")),
            "metadata": kwargs.get("metadata", {})
        }
        
        # Register participant and stake tokens
        return agent.connection_manager.connections["sonic"].register_participant(
            participant_data=participant_data
        )

    except Exception as e:
        logger.error(f"Failed to register participant: {str(e)}")
        return None

@register_action("create-shipment-contract")
def create_shipment(agent, **kwargs):
    """Create a new shipment smart contract
    """
    try:
        shipment_data = {
            "supplier": kwargs.get("supplier_address"),
            "receiver": kwargs.get("receiver_address"),
            "products": kwargs.get("products"),
            "temperature_range": kwargs.get("temperature_range"),
            "deadline": kwargs.get("deadline"),
            "payment_amount": float(kwargs.get("payment_amount"))
        }
        
        # Create shipment contract
        return agent.connection_manager.connections["sonic"].create_shipment(
            shipment_data=shipment_data
        )

    except Exception as e:
        logger.error(f"Failed to create shipment: {str(e)}")
        return None

@register_action("update-shipment-status")
def update_shipment_status(agent, **kwargs):
    """Update shipment status and conditions on blockchain
    """
    try:
        update_data = {
            "shipment_id": kwargs.get("shipment_id"),
            "status": kwargs.get("status"),
            "location": kwargs.get("location"),
            "temperature": float(kwargs.get("temperature")),
            "timestamp": kwargs.get("timestamp")
        }
        
        # Update shipment status
        return agent.connection_manager.connections["sonic"].update_shipment_status(
            update_data=update_data
        )

    except Exception as e:
        logger.error(f"Failed to update shipment status: {str(e)}")
        return None

@register_action("complete-shipment")
def complete_shipment(agent, **kwargs):
    """Complete shipment and trigger payment
    """
    try:
        completion_data = {
            "shipment_id": kwargs.get("shipment_id"),
            "quality_score": float(kwargs.get("quality_score")),
            "temperature_logs": kwargs.get("temperature_logs"),
            "delivery_proof": kwargs.get("delivery_proof")
        }
        
        # Complete shipment and release payment
        return agent.connection_manager.connections["sonic"].complete_shipment(
            completion_data=completion_data
        )

    except Exception as e:
        logger.error(f"Failed to complete shipment: {str(e)}")
        return None

@register_action("handle-temperature-breach")
def handle_temperature_breach(agent, **kwargs):
    """Handle temperature breach event and trigger penalties
    """
    try:
        breach_data = {
            "shipment_id": kwargs.get("shipment_id"),
            "temperature": float(kwargs.get("temperature")),
            "duration": int(kwargs.get("duration")),
            "severity": kwargs.get("severity"),
            "timestamp": kwargs.get("timestamp")
        }
        
        # Record breach and apply penalties
        return agent.connection_manager.connections["sonic"].handle_breach(
            breach_data=breach_data
        )

    except Exception as e:
        logger.error(f"Failed to handle temperature breach: {str(e)}")
        return None

@register_action("calculate-rewards")
def calculate_rewards(agent, **kwargs):
    """Calculate and distribute performance rewards
    """
    try:
        performance_data = {
            "participant": kwargs.get("participant_address"),
            "period": kwargs.get("period"),
            "metrics": kwargs.get("performance_metrics"),
            "reward_amount": float(kwargs.get("reward_amount"))
        }
        
        # Calculate and distribute rewards
        return agent.connection_manager.connections["sonic"].distribute_rewards(
            performance_data=performance_data
        )

    except Exception as e:
        logger.error(f"Failed to calculate rewards: {str(e)}")
        return None