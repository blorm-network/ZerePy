import logging
import os
from typing import Dict, Any, List
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
import eth_account
from eth_account.signers.local import LocalAccount
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

logger = logging.getLogger("connections.echochambers_connection")

class HyperliquidConnectionError(Exception):
    """Base exception for Hyperliquid connection errors"""
    pass

class HyperliquidConfigurationError(HyperliquidConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class HyperliquidAPIError(HyperliquidConnectionError):
    """Raised when Hyperliquid API requests fail"""
    pass

class HyperliquidConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.network = config.get("network")
        self.api_key = None
    
    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Hyperliquid configuration from JSON"""
        required_fields = ["network"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config['network'], str) or config['network'] not in ['mainnet', 'testnet']:
            raise ValueError("network must be either 'mainnet' or 'testnet'")
            
        return config
    
    def register_actions(self) -> None:
        """Register available Hyperliquid actions"""
        self.actions = {

        }

    def _get_credentials(self) -> Dict[str, str]:
        """Get Hyperliquid credentials from environment with validation"""
        logger.debug("Retrieving Hyperliquid credentials")
        load_dotenv()

        required_vars = {
            'HYPERLIQUID_API_KEY': 'api key',
        }

        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing Hyperliquid credentials: {', '.join(missing)}"
            raise HyperliquidConfigurationError(error_msg)

        logger.debug("All required credentials found")
        return credentials

    def configure(self) -> None:
        """Sets up Hyperliquid API authentication"""
        logger.info("Starting Hyperliquid authentication setup")

        # Check existing configuration
        if self.is_configured(verbose=False):
            logger.info("Hyperliquid API is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        setup_instructions = [
            "\n🐦 HYPERLIQUID AUTHENTICATION SETUP",
            "\n📝 To get your Hyperliquid API credentials:",
            "1. Go to https://app.hyperliquid.xyz/API",
            "2. Generate a new API Wallet and save the API Wallet Address and Private Key"
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        try:
            logger.info("\nPlease enter your Hyperliquid API Key:")
            credentials = {
                'api_key': input("Enter your API Key: ")
            }

            # Save credentials
            if not os.path.exists('.env'):
                logger.debug("Creating new .env file")
                with open('.env', 'w') as f:
                    f.write('')

            # Save to .env
            env_vars = {
                'HYPERLIQUID_API_KEY': credentials['api_key']
            }

            for key, value in env_vars.items():
                set_key('.env', key, value)
                logger.debug(f"Saved {key} to .env")

            logger.info("\n✅ Hyperliquid authentication successfully set up!")
            logger.info("Your API key has been stored in the .env file.")
            return True
        
        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            raise HyperliquidConfigurationError(error_msg)
        
    def is_configured(self, verbose = True) -> bool:
        """Check if Hyperliquid credentials are configured and valid"""
        logger.debug("Checking Hyperliquid configuration status")
        try:
            credentials = self._get_credentials()

            base_url = constants.MAINNET_API_URL if self.config['network'] == 'mainnet' else constants.TESTNET_API_URL

            account: LocalAccount = eth_account.Account.from_key(credentials["HYPERLIQUID_API_KEY"])
            if account.address != self.config['agent_wallet_address']:
                raise HyperliquidConfigurationError("Agent wallet address does not match the API key")

            logger.debug("Hyperliquid configuration is valid")
            return True
        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, HyperliquidConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False