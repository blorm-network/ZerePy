import logging
import os
import importlib
from typing import Dict, Any, List, Type, get_type_hints, Union
from dataclasses import is_dataclass
from eth_account import Account
from pydantic import BaseModel
from web3 import Web3
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
from src.action_handler import register_action
from goat.classes.plugin_base import PluginBase
from goat import ToolBase, WalletClientBase, get_tools
from goat_wallets.web3 import Web3EVMWalletClient

logger = logging.getLogger("connections.goat_connection")


class GoatConnectionError(Exception):
    """Base exception for Goat connection errors"""

    pass


class GoatConfigurationError(GoatConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class GoatConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("🐐 Initializing Goat connection...")

        self._is_configured = False
        self._wallet_client: WalletClientBase | None = None
        self._plugins: Dict[str, PluginBase] = {}
        self._action_registry: Dict[str, ToolBase] = {}
        self._config = self.validate_config(
            config
        )  # Store config but don't register actions yet

    def _resolve_type(self, raw_value: str, module) -> Any:
        """Resolve a type from a string, either from plugin module or fully qualified path"""
        try:
            # Try to load from plugin module first
            return getattr(module, raw_value)
        except AttributeError:
            try:
                # Try as fully qualified import
                module_path, class_name = raw_value.rsplit(".", 1)
                type_module = importlib.import_module(module_path)
                return getattr(type_module, class_name)
            except (ValueError, ImportError, AttributeError) as e:
                raise GoatConfigurationError(
                    f"Could not resolve type '{raw_value}'"
                ) from e

    def _validate_value(self, raw_value: Any, field_type: Type, module) -> Any:
        """Validate and convert a value to its expected type"""
        # Handle basic types
        if field_type in (str, int, float, bool):
            return field_type(raw_value)

        # Handle Lists
        if hasattr(field_type, "__origin__") and field_type.__origin__ is list:
            if not isinstance(raw_value, list):
                raise ValueError(f"Expected list, got {type(raw_value).__name__}")

            element_type = field_type.__args__[0]
            return [
                self._validate_value(item, element_type, module) for item in raw_value
            ]

        # Handle dynamic types (classes/types that need to be imported)
        if isinstance(raw_value, str):
            return self._resolve_type(raw_value, module)

        raise ValueError(f"Unsupported type: {field_type}")

    def _load_plugin(self, plugin_config: Dict[str, Any]) -> None:
        """Dynamically load plugins from goat_plugins namespace"""
        plugin_name = plugin_config["name"]
        try:
            # Import from goat_plugins namespace
            module = importlib.import_module(f"goat_plugins.{plugin_name}")

            # Get the plugin initializer function
            plugin_initializer = getattr(module, plugin_name)

            # Get the options type from the function's type hints
            type_hints = get_type_hints(plugin_initializer)
            if "options" not in type_hints:
                raise GoatConfigurationError(
                    f"Plugin '{plugin_name}' initializer must have 'options' parameter"
                )

            options_class = type_hints["options"]
            if not is_dataclass(options_class):
                raise GoatConfigurationError(
                    f"Plugin '{plugin_name}' options must be a dataclass"
                )

            # Get the expected fields and their types from the options class
            option_fields = get_type_hints(options_class)

            # Convert and validate the provided args
            validated_args = {}
            raw_args = plugin_config.get("args", {})

            for field_name, field_type in option_fields.items():
                if field_name not in raw_args:
                    raise GoatConfigurationError(
                        f"Missing required option '{field_name}' for plugin '{plugin_name}'"
                    )

                raw_value = raw_args[field_name]

                try:
                    validated_value = self._validate_value(
                        raw_value, field_type, module
                    )
                    validated_args[field_name] = validated_value

                except (ValueError, TypeError) as e:
                    raise GoatConfigurationError(
                        f"Invalid value for option '{field_name}' in plugin '{plugin_name}': {str(e)}"
                    ) from e

            # Create the options instance
            plugin_options = options_class(**validated_args)

            # Initialize the plugin
            plugin_instance: PluginBase = plugin_initializer(options=plugin_options)
            self._plugins[plugin_name] = plugin_instance
            logger.info(f"🐐 Loaded plugin: {plugin_name}")

        except ImportError:
            raise GoatConfigurationError(
                f"Failed to import plugin '{plugin_name}' from goat_plugins namespace"
            )
        except AttributeError as e:
            raise GoatConfigurationError(
                f"Plugin '{plugin_name}' does not have expected initializer function"
            )
        except Exception as e:
            raise GoatConfigurationError(
                f"Failed to initialize plugin '{plugin_name}': {str(e)}"
            )

    def _convert_pydantic_to_action_parameters(
        self, model_class: Type[BaseModel]
    ) -> List[ActionParameter]:
        """Convert Pydantic model fields to ActionParameters"""
        parameters = []

        for field_name, field in model_class.model_fields.items():
            # Get field type, handling Optional types
            field_type = field.annotation
            is_optional = False

            # Handle Optional types
            if field_type is not None:
                # Check if it's an Optional type
                origin = getattr(field_type, "__origin__", None)
                if origin is Union:
                    args = getattr(field_type, "__args__", None)
                    if args and type(None) in args:
                        # Get the non-None type from Optional
                        field_type = next(t for t in args if t is not type(None))
                        is_optional = True

            # Get description from Field
            description = field.description or f"Parameter {field_name}"

            # Ensure we have a valid Python type
            if not isinstance(field_type, type):
                # Default to str if we can't determine the type
                field_type = str

            parameters.append(
                ActionParameter(
                    name=field_name,
                    required=not is_optional,
                    type=field_type,
                    description=description,
                )
            )

        return parameters

    @property
    def is_llm_provider(self) -> bool:
        """Whether this connection provides LLM capabilities"""
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GOAT configuration"""
        required_fields = ["plugins"]
        required_plugin_fields = ["name", "args"]

        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )

        for plugin_config in config["plugins"]:
            missing_plugin_fields = [
                field for field in required_plugin_fields if field not in plugin_config
            ]
            if missing_plugin_fields:
                raise ValueError(
                    f"Missing required fields for plugin: {', '.join(missing_plugin_fields)}"
                )

            if not isinstance(plugin_config["args"], dict):
                raise ValueError("args must be a dictionary")

            for arg_name, arg_value in plugin_config["args"].items():
                if not isinstance(arg_name, str):
                    raise ValueError(f"Invalid key for {arg_name}: {arg_value}")

            plugin_name = plugin_config["name"]
            if not plugin_name.isidentifier():
                raise ValueError(
                    f"Invalid plugin name '{plugin_name}'. Must be a valid Python identifier"
                )

            self._load_plugin(plugin_config)

        return config

    def _register_actions_with_wallet(self) -> None:
        """Register actions with the current wallet client"""
        self.actions = {}  # Clear existing actions
        self._action_registry = {}  # Clear existing registry

        tools = get_tools(self._wallet_client, list(self._plugins.values()))  # type: ignore

        for tool in tools:
            action_parameters = self._convert_pydantic_to_action_parameters(
                tool.parameters
            )

            self.actions[tool.name] = Action(  # type: ignore
                name=tool.name,
                description=tool.description,
                parameters=action_parameters,
            )
            self._action_registry[tool.name] = tool

            register_action(tool.name)(
                lambda agent, tool_name=tool.name, **kwargs: self.perform_action(
                    tool_name, **kwargs
                )
            )

    def register_actions(self) -> None:
        """Initial action registration - deferred until wallet is configured"""
        pass  # We'll register actions after wallet configuration

    def _create_wallet(self) -> bool:
        """Create wallet from environment variables"""
        try:
            load_dotenv()
            rpc_url = os.getenv("GOAT_RPC_PROVIDER_URL")
            private_key = os.getenv("GOAT_WALLET_PRIVATE_KEY")

            if not rpc_url or not private_key:
                return False

            # Initialize Web3 and test connection
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                logger.error("Failed to connect to RPC provider")
                return False

            # Test private key by creating account
            try:
                account = Account.from_key(private_key)
                w3.eth.default_account = account.address
                self._wallet_client = Web3EVMWalletClient(w3)
                # Register actions now that we have a wallet
                self._register_actions_with_wallet()
                return True
            except Exception as e:
                logger.error(f"Invalid private key: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Failed to create wallet: {str(e)}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if the connection is properly configured"""
        if not self._is_configured:
            self._is_configured = self._create_wallet()

        if verbose and not self._is_configured:
            logger.error(
                "GOAT connection is not configured. Please run configure() first."
            )

        return self._is_configured

    def configure(self, **kwargs) -> bool:
        """Sets up GOAT configuration"""
        logger.info("Starting GOAT configuration setup")

        if self.is_configured(verbose=False):
            logger.info("GOAT API is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != "y":
                return False

        setup_instructions = [
            "\n🔗 GOAT CONFIGURATION SETUP",
            "\n📝 You will need:",
            "1. An RPC provider URL (e.g. from Infura, Alchemy, or your own node)",
            "2. A wallet private key for signing transactions",
            "\n⚠️ IMPORTANT: Never share your private key with anyone!",
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        try:
            # Get RPC URL and private key
            logger.info("\nPlease enter your credentials:")
            rpc_url = input("Enter your RPC provider URL: ")
            private_key = input(
                "Enter your wallet private key (will be stored in .env): "
            )

            # Basic validation
            if not rpc_url.startswith(("http://", "https://")):
                raise ValueError(
                    "Invalid RPC URL format. Must start with http:// or https://"
                )

            if not private_key.startswith("0x") or len(private_key) != 66:
                raise ValueError(
                    "Invalid private key format. Must be a 64-character hex string with '0x' prefix"
                )

            # Initialize Web3 and test connection
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                raise ConnectionError(
                    "Failed to connect to RPC provider. Please check your URL."
                )

            # Test private key by creating account
            try:
                account = Account.from_key(private_key)
                logger.info(f"\nWallet address: {account.address}")
            except Exception as e:
                raise ValueError(f"Invalid private key: {str(e)}")

            # Save to .env
            if not os.path.exists(".env"):
                logger.debug("Creating new .env file")
                with open(".env", "w") as f:
                    f.write("")

            env_vars = {
                "GOAT_RPC_PROVIDER_URL": rpc_url,
                "GOAT_WALLET_PRIVATE_KEY": private_key,
            }

            for key, value in env_vars.items():
                set_key(".env", key, value)
                logger.debug(f"Saved {key} to .env")

            # Initialize wallet client
            w3.eth.default_account = account.address
            self._wallet_client = Web3EVMWalletClient(w3)

            # Register actions now that we have a wallet
            self._register_actions_with_wallet()

            logger.info("\n✅ GOAT configuration successfully set up!")
            logger.info(
                "Your RPC URL and private key have been stored in the .env file."
            )

            self._is_configured = True
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            raise GoatConfigurationError(error_msg)

    def perform_action(self, action_name: str, **kwargs) -> Any:
        """Execute a GOAT action using a plugin's tool"""
        action = self.actions.get(action_name)
        if not action:
            raise KeyError(f"Unknown action: {action_name}")

        tool = self._action_registry[action_name]
        return tool.execute(kwargs)
