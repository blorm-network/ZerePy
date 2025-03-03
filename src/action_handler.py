import logging

import asyncio

logger = logging.getLogger("action_handler")

action_registry = {}    

def register_action(action_name):

    def decorator(func):

        action_registry[action_name] = func

        return func

    return decorator

def execute_action(agent, action_name, **kwargs):

    if action_name in action_registry:

        action = action_registry[action_name]

        

        # Check if the action is a coroutine function (async)

        if asyncio.iscoroutinefunction(action):

            # Create a new event loop to run the coroutine

            loop = asyncio.new_event_loop()

            try:

                # Run the coroutine to completion

                return loop.run_until_complete(action(agent, **kwargs))

            finally:

                loop.close()

        else:

            # Regular function, just call it

            return action(agent, **kwargs)

    else:

        logger.error(f"Action {action_name} not found")

        return None

def list_registered_actions():

    """Return a list of all registered action names"""

    return list(action_registry.keys())