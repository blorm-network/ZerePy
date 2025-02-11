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

@register_action("get_supported_chains")
def get_supported_chains(agent, **kwargs):
    """Get list of chains supported by deBridge for cross-chain transfers"""
    agent.logger.info("\n🔗 FETCHING SUPPORTED CHAINS")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="debridge",
            action_name="get_supported_chains",
            params={}
        )
        
        if result and result.get("chains"):
            agent.logger.info("\n✅ Retrieved supported chains successfully!")
            agent.logger.info("\nSupported Chains:")
            for chain in result["chains"]:
                agent.logger.info(f"• {chain['chainName']} (Chain ID: {chain['chainId']})")
            
        return {
            "status": "success",
            "chains": result.get("chains", []),
            "message": "Retrieved supported chains"
        }

    except Exception as e:
        agent.logger.error(f"\n❌ Failed to fetch supported chains: {str(e)}")
        return {"status": "error", "message": str(e)}

@register_action("get_tokens_info")
def get_tokens_info(agent, **kwargs):
    """Get information about tokens available for cross-chain bridging via deBridge protocol"""
    agent.logger.info("\n🪙 FETCHING TOKEN INFORMATION")
    try:
        # Get the parameters from command line arguments
        params = kwargs.get("params", [])
        if len(params) < 1:
            agent.logger.error("Not enough arguments. Expected: chainId [search_term]")
            return {"status": "error", "message": "Missing required parameters"}

        # Create parameters dict
        query_params = {
            "chainId": params[0],
        }
        
        # Add optional search term if provided
        if len(params) > 1:
            query_params["search"] = params[1]

        result = agent.connection_manager.perform_action(
            connection_name="debridge",
            action_name="get_tokens_info",
            params=query_params
        )
        
        if result and result.get("tokens"):
            agent.logger.info("\n✅ Retrieved token information successfully!")
            agent.logger.info("\nTokens:")
            
            # Limit output to prevent token consumption issues
            token_list = list(result["tokens"].items())
            display_count = min(5, len(token_list))  # Show at most 5 tokens
            
            for address, token in token_list[:display_count]:
                agent.logger.info(f"• {token['symbol']} ({token['name']}) - {address}")
                
            if len(token_list) > display_count:
                agent.logger.info(f"\n... and {len(token_list) - display_count} more tokens")
            
        return {
            "status": "success",
            "tokens": result.get("tokens", {}),
            "message": f"Retrieved tokens for chain {params[0]}"
        }

    except Exception as e:
        agent.logger.error(f"\n❌ Failed to fetch token information: {str(e)}")
        return {"status": "error", "message": str(e)}

@register_action("execute_bridge_tx")
def execute_bridge_transaction(agent, **kwargs):
    """Execute a previously created bridge transaction"""
    agent.logger.info("\n🚀 EXECUTING BRIDGE TRANSACTION")
    try:
        # Get the pending transaction from agent state
        pending_tx = agent.state.get("pending_bridge_tx")
        if not pending_tx:
            agent.logger.error("No pending bridge transaction found. Please create one first using create_bridge_tx.")
            return {"status": "error", "message": "No pending bridge transaction"}

        # Execute the transaction
        result = agent.connection_manager.perform_action(
            connection_name="debridge",
            action_name="execute_bridge_tx",
            params={"tx_data": pending_tx}
        )
        
        if result and result.get("signature"):
            agent.logger.info("\n✅ Bridge transaction executed successfully!")
            agent.logger.info(f"\nTransaction signature: {result['signature'][:10]}...")
            
            # Clear the pending transaction from state
            agent.state.pop("pending_bridge_tx", None)
            
        return {
            "status": "success",
            "signature": result.get("signature"),
            "message": f"Successfully executed bridge transaction. Signature: {result.get('signature', '')[:10]}..."
        }

    except Exception as e:
        agent.logger.error(f"\n❌ Failed to execute bridge transaction: {str(e)}")
        return {"status": "error", "message": str(e)}
