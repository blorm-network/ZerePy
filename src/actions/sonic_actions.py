import logging
import os
from dotenv import load_dotenv
from src.action_handler import register_action

logger = logging.getLogger("actions.sonic_actions")

# Note: These action handlers are currently simple passthroughs to the sonic_connection methods.
# They serve as hook points where hackathon participants can add custom logic, validation,
# or additional processing before/after calling the underlying connection methods.
# Feel free to modify these handlers to add your own business logic!

@register_action("get-token-by-ticker")
def get_token_by_ticker(agent, **kwargs):
    """Get token address by ticker symbol
    """
    try:
        ticker = kwargs.get("ticker")
        if not ticker:
            logger.error("No ticker provided")
            return None
            
        # Direct passthrough to connection method - add your logic before/after this call!
        agent.connection_manager.connections["sonic"].get_token_by_ticker(ticker)

        return

    except Exception as e:
        logger.error(f"Failed to get token by ticker: {str(e)}")
        return None

@register_action("get-sonic-balance")
def get_sonic_balance(agent, **kwargs):
    """Get $S or token balance.
    """
    try:
        address = kwargs.get("address")
        token_address = kwargs.get("token_address")
        
        if not address:
            load_dotenv()
            private_key = os.getenv('SONIC_PRIVATE_KEY')
            web3 = agent.connection_manager.connections["sonic"]._web3
            account = web3.eth.account.from_key(private_key)
            address = account.address

        # Direct passthrough to connection method - add your logic before/after this call!
        agent.connection_manager.connections["sonic"].get_balance(
            address=address,
            token_address=token_address
        )
        return

    except Exception as e:
        logger.error(f"Failed to get balance: {str(e)}")
        return None

@register_action("send-sonic")
def send_sonic(agent, **kwargs):
    """Send $S tokens to an address.
    This is a passthrough to sonic_connection.transfer().
    Add your custom logic here if needed!
    """
    try:
        to_address = kwargs.get("to_address")
        amount = float(kwargs.get("amount"))

        # Direct passthrough to connection method - add your logic before/after this call!
        agent.connection_manager.connections["sonic"].transfer(
            to_address=to_address,
            amount=amount
        )
        return

    except Exception as e:
        logger.error(f"Failed to send $S: {str(e)}")
        return None

@register_action("send-sonic-token")
def send_sonic_token(agent, **kwargs):
    """Send tokens on Sonic chain.
    This is a passthrough to sonic_connection.transfer().
    Add your custom logic here if needed!
    """
    try:
        to_address = kwargs.get("to_address")
        token_address = kwargs.get("token_address")
        amount = float(kwargs.get("amount"))

        # Direct passthrough to connection method - add your logic before/after this call!
        agent.connection_manager.connections["sonic"].transfer(
            to_address=to_address,
            amount=amount,
            token_address=token_address
        )
        return

    except Exception as e:
        logger.error(f"Failed to send tokens: {str(e)}")
        return None

@register_action("swap-sonic")
def swap_sonic(agent, **kwargs):
    """Swap tokens on Sonic chain.
    This is a passthrough to sonic_connection.swap().
    Add your custom logic here if needed!
    """
    try:
        token_in = kwargs.get("token_in")
        token_out = kwargs.get("token_out") 
        amount = float(kwargs.get("amount"))
        slippage = float(kwargs.get("slippage", 0.5))

        # Direct passthrough to connection method - add your logic before/after this call!
        agent.connection_manager.connections["sonic"].swap(
            token_in=token_in,
            token_out=token_out,
            amount=amount,
            slippage=slippage
        )
        return 

    except Exception as e:
        logger.error(f"Failed to swap tokens: {str(e)}")
        return None