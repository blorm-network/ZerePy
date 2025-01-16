import logging
from src.action_handler import register_action

logger = logging.getLogger("agent")


@register_action("agentipy-transfer")
def agentipy_transfer(agent, **kwargs):
    """Transfer SOL or SPL tokens"""
    agent.logger.info("\n💸 INITIATING TRANSFER")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="transfer",
            params=[
                kwargs.get("to_address"),
                kwargs.get("amount"),
                kwargs.get("token_mint", None),
            ],
        )
        agent.logger.info("✅ Transfer completed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Transfer failed: {str(e)}")
        return False


@register_action("agentipy-swap")
def agentipy_swap(agent, **kwargs):
    """Swap tokens using Jupiter"""
    agent.logger.info("\n🔄 INITIATING TOKEN SWAP")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="trade",
            params=[
                kwargs.get("output_mint"),
                kwargs.get("input_amount"),
                kwargs.get("input_mint", None),
                kwargs.get("slippage_bps", 100),
            ],
        )
        agent.logger.info("✅ Swap completed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Swap failed: {str(e)}")
        return False


@register_action("agentipy-balance")
def agentipy_balance(agent, **kwargs):
    """Check SOL or token balance"""
    agent.logger.info("\n💰 CHECKING BALANCE")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="get-balance",
            params=[kwargs.get("token_address", None)],
        )
        agent.logger.info(f"Balance: {result}")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Balance check failed: {str(e)}")
        return None


@register_action("agentipy-stake")
def agentipy_stake(agent, **kwargs):
    """Stake SOL"""
    agent.logger.info("\n🎯 INITIATING SOL STAKE")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="stake",
            params=[kwargs.get("amount")],
        )
        agent.logger.info("✅ Staking completed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Staking failed: {str(e)}")
        return False


@register_action("agentipy-lend")
def agentipy_lend(agent, **kwargs):
    """Lend assets using Lulo"""
    agent.logger.info("\n🏦 INITIATING LENDING")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="lend-assets",
            params=[kwargs.get("amount")],
        )
        agent.logger.info("✅ Lending completed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Lending failed: {str(e)}")
        return False


@register_action("agentipy-request-funds")
def request_faucet_funds(agent, **kwargs):
    """Request faucet funds for testing"""
    agent.logger.info("\n🚰 REQUESTING FAUCET FUNDS")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy", action_name="request-faucet", params=[]
        )
        agent.logger.info("✅ Faucet request completed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Faucet request failed: {str(e)}")
        return False


@register_action("agentipy-deploy-token")
def agentipy_deploy_token(agent, **kwargs):
    """Deploy a new token"""
    agent.logger.info("\n🪙 DEPLOYING NEW TOKEN")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="deploy-token",
            params=[kwargs.get("decimals", 9)],
        )
        agent.logger.info("✅ Token deployed!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Token deployment failed: {str(e)}")
        return False


@register_action("agentipy-get-price")
def agentipy_get_price(agent, **kwargs):
    """Get token price"""
    agent.logger.info("\n💲 FETCHING TOKEN PRICE")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="fetch-price",
            params=[kwargs.get("token_id")],
        )
        agent.logger.info(f"Price: {result}")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Price fetch failed: {str(e)}")
        return None


@register_action("agentipy-get-tps")
def agentipy_get_tps(agent, **kwargs):
    """Get current Solana TPS"""
    agent.logger.info("\n📊 FETCHING CURRENT TPS")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy", action_name="get-tps", params=[]
        )
        agent.logger.info(f"Current TPS: {result}")
        return result
    except Exception as e:
        agent.logger.error(f"❌ TPS fetch failed: {str(e)}")
        return None


@register_action("agentipy-get-token-by-ticker")
def get_token_data_by_ticker(agent, **kwargs):
    """Get token data by ticker"""
    agent.logger.info("\n🔍 FETCHING TOKEN DATA BY TICKER")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="get-token-by-ticker",
            params=[kwargs.get("ticker")],
        )
        agent.logger.info("✅ Token data retrieved!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Token data fetch failed: {str(e)}")
        return None


@register_action("agentipy-get-token-by-address")
def get_token_data_by_address(agent, **kwargs):
    """Get token data by address"""
    agent.logger.info("\n🔍 FETCHING TOKEN DATA BY ADDRESS")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="get-token-by-address",
            params=[kwargs.get("mint")],
        )
        agent.logger.info("✅ Token data retrieved!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Token data fetch failed: {str(e)}")
        return None


@register_action("agentipy-launch-pump-token")
def launch_pump_fun_token(agent, **kwargs):
    """Launch a Pump & Fun token"""
    agent.logger.info("\n🚀 LAUNCHING PUMP & FUN TOKEN")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="agentipy",
            action_name="launch-pump-token",
            params=[
                kwargs.get("token_name"),
                kwargs.get("token_ticker"),
                kwargs.get("description"),
                kwargs.get("image_url"),
                kwargs.get("options", {}),
            ],
        )
        agent.logger.info("✅ Token launched successfully!")
        return result
    except Exception as e:
        agent.logger.error(f"❌ Token launch failed: {str(e)}")
        return False
