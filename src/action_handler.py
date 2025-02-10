import logging
import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar, Optional

logger = logging.getLogger("action_handler")

T = TypeVar('T')
action_registry = {}

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator that implements retry logic with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (will be multiplied by attempt number)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error: Optional[Exception] = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Action failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay:.1f}s: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Action failed after {max_retries} attempts: {str(e)}"
                        )
            
            if last_error:
                raise last_error
            return None  # Should never reach here
        return wrapper
    return decorator

def register_action(action_name: str):
    """Register an action in the global registry"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        action_registry[action_name] = func
        return func
    return decorator

async def execute_action(agent: Any, action_name: str, **kwargs) -> Any:
    """
    Execute a registered action with retry logic
    
    Args:
        agent: Agent instance
        action_name: Name of the registered action
        **kwargs: Arguments to pass to the action
        
    Returns:
        Result of the action execution
        
    Raises:
        KeyError if action is not found
        Exception if action execution fails after retries
    """
    if action_name in action_registry:
        action = action_registry[action_name]
        return await with_retry()(action)(agent, **kwargs)
    else:
        logger.error(f"Action {action_name} not found")
        return None
    

