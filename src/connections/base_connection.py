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
            # Connection state tracking
            self._initialized = False
            self._closed = False
            
            # Dictionary to store action name -> handler method mapping
            self.actions: Dict[str, Callable] = {}
            # Dictionary to store some essential configuration
            self.config = self.validate_config(config)
            
            # Initialize connection
            self._setup()
            self._initialized = True
        except Exception as e:
            logging.error("Could not initialize the connection")
            self._cleanup()
            raise ConnectionError(f"Failed to initialize connection: {e}")
    
    def _setup(self):
        """Initialize connection resources and register actions"""
        try:
            self.register_actions()
        except Exception as e:
            raise ConnectionError(f"Failed to setup connection: {e}")
    
    def _cleanup(self):
        """Clean up connection resources"""
        if not self._closed:
            try:
                self.actions.clear()
                self._closed = True
            except Exception as e:
                logging.error(f"Error during connection cleanup: {e}")
    
    def __del__(self):
        """Ensure resources are cleaned up on deletion"""
        if not self._closed:
            self._cleanup()

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

    def perform_action(self, action_name: str, **kwargs) -> Any:
        """
        Perform a registered action with the given parameters.
        
        Args:
            action_name: Name of the action to perform
            **kwargs: Parameters for the action
            
        Returns:
            Any: Result of the action
            
        Raises:
            KeyError: If the action is not registered
            ValueError: If the action parameters are invalid
        """
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")
            
        handler = self.actions[action_name]
        return handler(**kwargs)
