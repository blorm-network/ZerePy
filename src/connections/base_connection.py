import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable
from dataclasses import dataclass

@dataclass
class ActionParameter:
    name: str
    required: bool
    type: type
    description: str

@dataclass
class Action:
    name: str
    parameters: List[ActionParameter]
    description: str
    
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        errors = []
        for param in self.parameters:
            if param.required and param.name not in params:
                errors.append(f"Missing required parameter: {param.name}")
            elif param.name in params:
                try:
                    params[param.name] = param.type(params[param.name])
                except ValueError:
                    errors.append(f"Invalid type for {param.name}. Expected {param.type.__name__}")
        return errors

class BaseConnection(ABC):
    def __init__(self, config):
        try:
            # Dictionary to store action name -> handler method mapping
            self.actions: Dict[str, Callable] = {}
            # Dictionary to store some essential configuration
            self.config = self.validate_config(config) 
            # Register actions during initialization
            self.register_actions()
        except Exception as e:
            logging.error("Could not initialize the connection")
            raise e

    @property
    @abstractmethod
    def is_llm_provider(self):
        pass

    @abstractmethod
    def validate_config(self, config) -> Dict[str, Any]:
        """
        Validate config from JSON

        Args:
            config: dictionary containing all the config values for that connection
        
        Returns:
            Dict[str, Any]: Returns the config if valid
        
        Raises:
            Error if the configuration is not valid
        """

    @abstractmethod
    def configure(self, **kwargs) -> bool:
        """
        Configure the connection with necessary credentials.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        pass

    @abstractmethod
    def is_configured(self, verbose = False) -> bool:
        """
        Check if the connection is properly configured and ready for use.
        
        Returns:
            bool: True if the connection is configured, False otherwise
        """
        pass

    @abstractmethod
    def register_actions(self) -> None:
        """
        Register all available actions for this connection.
        Should populate self.actions with action_name -> handler mappings.
        """
        pass

    def perform_action(self, action_name: str, params: List[Any] = None, **kwargs) -> Any:
        """
        Perform a registered action with the given parameters.
        
        Args:
            action_name: Name of the action to perform
            params: List of positional parameters for the action
            **kwargs: Additional keyword parameters for the action
        
        Returns:
            Any: Result of the action
        
        Raises:
            KeyError: If the action is not registered
            ValueError: If the action parameters are invalid
        """
        # Parse action_name if it contains parameters (e.g., "action:param1:param2:param3")
        if ":" in action_name:
            parts = action_name.split(":")
            base_action = parts[0]
            embedded_params = parts[1:]
            
            if base_action in self.actions:
                action_name = base_action
                # Add embedded params to the params list
                if params is None:
                    params = embedded_params
                else:
                    params = embedded_params + list(params)
        
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")
        
        action_def = self.actions[action_name]
        
        # Find the actual handler
        if isinstance(action_def, Action):
            # Extract parameter mappings
            param_dict = {}
            if params and hasattr(action_def, 'parameters'):
                for i, param_def in enumerate(action_def.parameters):
                    if i < len(params):
                        try:
                            # Try to convert according to expected type
                            param_dict[param_def.name] = param_def.type(params[i])
                        except (ValueError, TypeError):
                            # Fall back to string if conversion fails
                            param_dict[param_def.name] = params[i]
            
            # Add any keyword arguments
            param_dict.update(kwargs)
            
            # Handle different implementations of the action pattern
            handler_name = action_name.replace('-', '_')
            if hasattr(self, handler_name):
                # Method on the class
                handler = getattr(self, handler_name)
                return handler(**param_dict)
            else:
                # Standalone handler
                return action_def(**param_dict)
        else:
            # Direct function reference
            handler = action_def
            
            # If we have params, try to build kwargs from them
            if params:
                # For direct function references, we just pass the parameters as positional arguments
                return handler(*params, **kwargs)
            else:
                return handler(**kwargs)