import logging

logger = logging.getLogger("agent")

action_registry = {}    

def register_action(action_name):
    def decorator(func):
        action_registry[action_name] = func
        return func
    return decorator

def execute_action(agent, action_name, **kwargs):
    if action_name in action_registry:
       return action_registry[action_name](agent, **kwargs)
    else:
        logger.error(f"Action {action_name} not found")
        return None
    

