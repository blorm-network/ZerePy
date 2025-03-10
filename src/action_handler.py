# In your action_handler.py
import logging
import asyncio
from functools import wraps

logger = logging.getLogger("action_handler")
action_registry = {}

def register_action(action_name):
    def decorator(func):
        action_registry[action_name] = func
        return func
    return decorator

async def execute_action(agent, action_name, **kwargs):
    """Execute a registered action, handling both sync and async functions properly"""
    if action_name not in action_registry:
        logger.error(f"Action {action_name} not found")
        return None
        
    action = action_registry[action_name]
    
    # Check if the action is a coroutine function (async)
    if asyncio.iscoroutinefunction(action):
        # Directly await the coroutine
        return await action(agent, **kwargs)
    else:
        # Regular function, just call it
        return action(agent, **kwargs)

def list_registered_actions():
    """Return a list of all registered action names"""
    return list(action_registry.keys())