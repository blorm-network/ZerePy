import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable, Union, TypeVar
from dataclasses import dataclass
from src.types.config import BaseConnectionConfig

@dataclass
class ActionParameter:
    name: str
    required: bool
    type: type
    description: str

@dataclass
class Action:
    name: str
    method: Callable[..., Any]
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
        
    def __call__(self, **kwargs: Any) -> Any:
        """Make Action instances callable like regular methods"""
        errors = self.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")
        return self.method(**kwargs)

T = TypeVar('T', bound=BaseConnectionConfig)

class BaseConnection(ABC):
    config: BaseConnectionConfig
    actions: Dict[str, Union[Action, Callable[..., Any]]]

    def __init__(self, config: Union[Dict[str, Any], BaseConnectionConfig]) -> None:
        try:
            # Dictionary to store action name -> handler method mapping
            self.actions = {}
            
            # Handle both dict and BaseConnectionConfig inputs for backward compatibility
            if isinstance(config, dict):
                config = self.validate_config(config)
            elif not isinstance(config, BaseConnectionConfig):
                raise ValueError("Config must be either a dict or BaseConnectionConfig instance")
                
            # Store validated configuration
            self.config = config
            
            # Register actions during initialization
            self.register_actions()
        except Exception as e:
            logging.error("Could not initialize the connection")
            raise e

    @property
    @abstractmethod
    def is_llm_provider(self) -> bool:
        """Return whether this connection is an LLM provider"""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """
        Validate config from JSON and convert to appropriate ConnectionConfig type

        Args:
            config: dictionary containing all the config values for that connection
        
        Returns:
            BaseConnectionConfig: Returns the validated config as a Pydantic model
        
        Raises:
            Error if the configuration is not valid
        """

    @abstractmethod
    def configure(self, **kwargs: Any) -> bool:
        """
        Configure the connection with necessary credentials.
        
        Args:
            **kwargs: Configuration parameters
            
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        pass

    @abstractmethod
    def is_configured(self, verbose: bool = False) -> bool:
        """
        Check if the connection is properly configured and ready for use.
        
        Args:
            verbose: Whether to print additional configuration details
            
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

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """
        Perform a registered action with the given parameters.
        
        Args:
            action_name: Name of the action to perform
            **kwargs: Parameters for the action
            
        Returns:
            Any: Result of the action
            
        Raises:
            KeyError: If the action is not registered
            ValueError: If the action parameters are invalid or config is not properly set
        """
        if not isinstance(self.config, BaseConnectionConfig):
            raise ValueError("Connection not properly configured with Pydantic model")
            
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")
            
        action = self.actions[action_name]
        if isinstance(action, Action):
            errors = action.validate_params(kwargs)
            if errors:
                raise ValueError(f"Invalid parameters: {', '.join(errors)}")
            return action.method(**kwargs)
        return action(**kwargs)  # For backward compatibility with direct method references
