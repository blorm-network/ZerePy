import logging
from src.action_handler import register_action

logger = logging.getLogger("actions.debridge_actions")

@register_action("create-bridge-tx")
def create_bridge_tx(agent, **kwargs):
    """Create Bridge TX using Debridge"""
    try:
        required_args = ['connection', 'srcChainId', 'srcChainTokenIn', 'srcChainTokenInAmount', 'dstChainId', 'dstChainTokenOut', 'dstChainTokenOutRecipient']
        for arg in required_args:
            if arg not in kwargs:
                logger.error(f"Missing required argument: {arg}")
                return None

        response = agent.connection_manager.connections["debridge"].create_bridge_tx(
            connection=kwargs['connection'],
            srcChainId=kwargs['srcChainId'],
            srcChainTokenIn=kwargs['srcChainTokenIn'],
            srcChainTokenInAmount=kwargs['srcChainTokenInAmount'],
            dstChainId=kwargs['dstChainId'],
            dstChainTokenOut=kwargs['dstChainTokenOut'],
            dstChainTokenOutRecipient=kwargs['dstChainTokenOutRecipient'],
            dstChainTokenOutAmount=kwargs.get('dstChainTokenOutAmount', "auto"),
            dstChainOrderAuthorityAddress=kwargs.get('dstChainOrderAuthorityAddress'),
            affiliateFeeRecipient=kwargs.get('affiliateFeeRecipient'),
            prependOperatingExpense=kwargs.get('prependOperatingExpense', True),
            affiliateFeePercent=kwargs.get('affiliateFeePercent', 0),
            dlnHook=kwargs.get('dlnHook')
        )
        return response
    except Exception as e:
        logger.error(f"Failed to create bridge transaction: {str(e)}")
        return None

@register_action("get-order-status")
def get_order_status(agent, **kwargs):
    """Get order status using Debridge"""
    try:
        response = agent.connection_manager.connections["debridge"].get_order_status(
            id=kwargs.get('id'),
            hash=kwargs.get('hash')
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get order status: {str(e)}")
        return None

@register_action("get-order-details")
def get_order_details(agent, **kwargs):
    """Get order details using Debridge"""
    try:
        if 'id' not in kwargs:
            logger.error("Missing required argument: id")
            return None

        response = agent.connection_manager.connections["debridge"].get_order_details(
            id=kwargs['id']
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get order details: {str(e)}")
        return None

@register_action("cancel-tx")
def cancel_tx(agent, **kwargs):
    """Cancel transaction using Debridge"""
    try:
        if 'id' not in kwargs:
            logger.error("Missing required argument: id")
            return None

        response = agent.connection_manager.connections["debridge"].cancel_tx(
            id=kwargs['id']
        )
        return response
    except Exception as e:
        logger.error(f"Failed to cancel transaction: {str(e)}")
        return None

@register_action("extcall-cancel-tx")
def extcall_cancel_tx(agent, **kwargs):
    """External call to cancel transaction using Debridge"""
    try:
        if 'id' not in kwargs:
            logger.error("Missing required argument: id")
            return None

        response = agent.connection_manager.connections["debridge"].extcall_cancel_tx(
            id=kwargs['id']
        )
        return response
    except Exception as e:
        logger.error(f"Failed to perform external call to cancel transaction: {str(e)}")
        return None

@register_action("get-supported-chains")
def get_supported_chains(agent, **kwargs):
    """Get supported chains using Debridge"""
    try:
        response = agent.connection_manager.connections["debridge"].get_supported_chains()
        return response
    except Exception as e:
        logger.error(f"Failed to get supported chains: {str(e)}")
        return None

@register_action("get-token-list")
def get_token_list(agent, **kwargs):
    """Get token list using Debridge"""
    try:
        if 'chainId' not in kwargs:
            logger.error("Missing required argument: chainId")
            return None

        response = agent.connection_manager.connections["debridge"].get_token_list(
            chainId=kwargs['chainId']
        )
        return response
    except Exception as e:
        logger.error(f"Failed to get token list: {str(e)}")
        return None

@register_action("execute-bridge-tx")
def execute_bridge_tx(agent, **kwargs):
    """Execute bridge transaction using Debridge"""
    try:
        if 'connection' not in kwargs:
            logger.error("Missing required argument: connection")
            return None

        response = agent.connection_manager.connections["debridge"].execute_bridge_tx(
            connection=kwargs['connection'],
            compute_unit_price=kwargs.get('compute_unit_price', 200_000),
            compute_unit_limit=kwargs.get('compute_unit_limit')
        )
        return response
    except Exception as e:
        logger.error(f"Failed to execute bridge transaction: {str(e)}")
        return None
