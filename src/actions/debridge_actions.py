import time 
from src.action_handler import register_action
from src.helpers import print_h_bar

@register_action("create_bridge_tx")
def create_bridge_transaction(agent, **kwargs):
    """Create a cross-chain bridging transaction"""
    agent.logger.info("\n🌉 CREATING BRIDGE TRANSACTION")
    try:
        # Get the parameters from command line arguments
        params = kwargs.get("params", [])
        if len(params) < 6:
            agent.logger.error("Not enough arguments. Expected: srcChainId srcChainTokenIn srcChainTokenInAmount dstChainId dstChainTokenOut dstChainTokenOutRecipient")
            return {"status": "error", "message": "Missing required parameters"}

        # Create transaction with command line parameters
        result = agent.connection_manager.perform_action(
            connection_name="debridge",
            action_name="create_bridge_tx",
            params={
                "srcChainId": params[0],
                "srcChainTokenIn": params[1],
                "srcChainTokenInAmount": params[2],
                "dstChainId": params[3],
                "dstChainTokenOut": params[4],
                "dstChainTokenOutRecipient": params[5]
            }
        )

        # Store transaction data in agent state for later execution
        agent.state["pending_bridge_tx"] = result
        
        # Print transaction details
        if result:
            agent.logger.info("\n✅ Bridge transaction created successfully!")
            agent.logger.info("\nTransaction Details:")
            agent.logger.info(f"Order ID: {result['orderId']}")
            agent.logger.info(f"Source: {result['estimation']['srcChainTokenIn']['amount']} {result['estimation']['srcChainTokenIn']['symbol']} (${result['estimation']['srcChainTokenIn']['approximateUsdValue']:.2f})")
            agent.logger.info(f"Destination: {result['estimation']['dstChainTokenOut']['amount']} {result['estimation']['dstChainTokenOut']['symbol']} (${result['estimation']['dstChainTokenOut']['approximateUsdValue']:.2f})")
            agent.logger.info(f"Slippage: {result['estimation']['recommendedSlippage']}%")
            agent.logger.info(f"Expected Delay: {result['order']['approximateFulfillmentDelay']} seconds")
            
        return {"status": "success", "tx_data": result}

    except Exception as e:
        agent.logger.error(f"\n❌ Failed to create bridge transaction: {str(e)}")
        return {"status": "error", "message": str(e)}

# @register_action("execute_bridge_tx")
# def execute_bridge_transaction(agent, **kwargs):
#     """Execute a previously created bridge transaction"""
#     agent.logger.info("\n🚀 EXECUTING BRIDGE TRANSACTION")
#     try:
#         # Execute the transaction using stored data in the connection
#         result = agent.connection_manager.perform_action(
#             connection_name="debridge",
#             action_name="execute_bridge_tx",
#             kwargs={}  # No parameters needed
#         )
        
#         if result:
#             agent.logger.info("\n✅ Bridge transaction executed successfully!")
#             agent.logger.info(f"Order ID: {result.get('orderId')}")
            
#         return {"status": "success", "result": result}
        
#     except Exception as e:
#         agent.logger.error(f"\n❌ Failed to execute bridge transaction: {str(e)}")
#         return {"status": "error", "message": str(e)}
