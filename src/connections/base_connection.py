import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable
from dataclasses import dataclass
from langgraph.prebuilt import ToolExecutor

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

    def __dict__(self) -> dict:
        # Convert action to dict object
        action_dict = {self.name :
                           {"description": self.description,
                            "parameters": [
                                {
                                    "name": param.name,
                                    "required": param.required,
                                    "type": param.type.__name__,
                                    "description": param.description
                                }
                                for param in self.parameters
                            ],
                            }
                       }
        return action_dict

    def __str__(self) -> str:
        # Convert action to string
        return json.dumps(self.__dict__(), indent=4)

class BaseConnection(ABC):
    def __init__(self, config):
        try:
            # Dictionary to store action name -> handler method mapping
            self.actions: Dict[str, Callable] = {}
            # Dictionary to store some essential configuration
            self.config = self.validate_config(config) 
            # Register actions during initialization
            self.register_actions()
        #Create tool executor for registered actions 
            tools = [self._create_tool(action) for action in self.actions.values()]
            self.tool_executor = ToolExecutor(tools)
        except Exception as e:
            logging.error("Could not initialize the connection")
            raise e
    
    def _create_tool(self, action: Action) -> Callable:
        """Convert an Action to a LangGraph tool format"""

        def tool_wrapper(tool_input: dict):
            print(f"Tool invoked: {action.name} with arguments: {tool_input}")
            missing_params = [param.name for param in action.parameters if param.required and param.name not in tool_input]
            all_required_params = [param.name for param in action.parameters if param.required]

            if missing_params:
                print(f"⚠️ Missing required parameters for {action.name}: {missing_params}")
                return {
                    "status": "missing_params",
                    "message": f"Missing required parameters for {action.name}: {', '.join(missing_params)} , retry with all required parameters",
                    "missing_params": missing_params,
                    "required_params": all_required_params
                }

            return self.perform_action(action.name, kwargs=tool_input)
        
        connection_name = self.__class__.__name__.lower().replace('connection', '')
        connection_prefixed_name = f"{connection_name}_{action.name}"
    
        tool_wrapper.__name__ = connection_prefixed_name
        tool_wrapper.__doc__ = action.description

        tool_wrapper.__annotations__ = {
                        param.name: {'type': param.type,'description': param.description}
                        for param in action.parameters
                            if param.required
                        }
        return tool_wrapper

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

    def __str__(self):
        # Convert dict object to string
        return json.dumps(self.__dict__(), indent=4)

    def __dict__(self):
        # Create a dict object of the connection
        connection_dict = {
            self.__class__.__name__ : {
                "is_llm_provider": self.is_llm_provider,
                "actions": [action.__dict__() for action in self.actions.values()]
            }
        }
        return connection_dict
