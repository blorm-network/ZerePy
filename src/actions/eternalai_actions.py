import logging
from src.action_handler import register_action

logger = logging.getLogger("action_handler")

@register_action("eternai-generate")
def eternai_generate(agent, **kwargs):
    """Generate text using EternalAI models"""
    logger.info("\n🤖 GENERATING TEXT WITH ETERNAI")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="eternalai",
            action_name="generate-text",
            params=[
                kwargs.get('prompt'),
                kwargs.get('system_prompt', agent._construct_system_prompt()),
                kwargs.get('model', None)
            ]
        )
        logger.info("✅ Text generation completed!")
        return result
    except Exception as e:
        logger.error(f"❌ Text generation failed: {str(e)}")
        return None

@register_action("eternai-check-model")
def eternai_check_model(agent, **kwargs):
    """Check if a specific model is available"""
    logger.info("\n🔍 CHECKING MODEL AVAILABILITY")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="eternalai",
            action_name="check-model",
            params=[kwargs.get('model')]
        )
        status = "available" if result else "not available"
        logger.info(f"Model is {status}")
        return result
    except Exception as e:
        logger.error(f"❌ Model check failed: {str(e)}")
        return False

@register_action("eternai-list-models")
def eternai_list_models(agent, **kwargs):
    """List all available EternalAI models"""
    logger.info("\n📋 LISTING AVAILABLE MODELS")
    try:
        result = agent.connection_manager.perform_action(
            connection_name="eternalai",
            action_name="list-models",
            params=[]
        )
        logger.info("✅ Models listed successfully!")
        return result
    except Exception as e:
        logger.error(f"❌ Model listing failed: {str(e)}")
        return None