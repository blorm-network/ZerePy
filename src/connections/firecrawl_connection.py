import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from firecrawl import FirecrawlApp


logger = logging.getLogger(__name__)

class FirecrawlConnectionError(Exception):
    """Base exception for FireCrawl connection errors"""
    pass


class FirecrawlConfigurationError(FirecrawlConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class FirecrawlAPIError(FirecrawlConnectionError):
    """Raised when Firecrawl API requests fail"""
    pass

class FirecrawlConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Firecrawl configuration from JSON"""
        required_fields = []
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")            
    
        return config

    def register_actions(self) -> None:
        """Register available Firecrawl actions"""
        self.actions = {
            "scrape-page": Action(
                name = "scrape-page",
                parameters = [
                    ActionParameter("url", True, str, "The URL of the page to scrape"),
                ],
                description = "Scrape a page for text data"
            )
        }

    def _get_client(self) -> FirecrawlApp:
        """Get or create Firecrawl app client"""
        if not self._client:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if not api_key:
                raise FirecrawlConfigurationError("Firecrawl API key not found in environment")
            self._client = FirecrawlApp(api_key=api_key)
        return self._client

    def configure(self) -> bool:
        """Sets up Firecrawl authentication"""
        print("\n🌍 Firecrawl API SETUP")

        if self.is_configured():
            print("\Firecrawl API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        print("\n📝 To get your Firecrawl API credentials:")
        print("1. Go to https://www.firecrawl.dev/app/api-keys")
        print("2. Navigate to the API keys section and create a new API key")
        
        api_key = input("\nEnter your Firecrawl API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'FIRECRAWL_API_KEY', api_key)
            
            client = FirecrawlApp(api_key=api_key)
      
            print("\n✅ Firecrawl API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Firecrawl API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('FIRECRAWL_API_KEY')
            if not api_key:
                return False

            client = FirecrawlApp(api_key=api_key)
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False
        

    def scrape_page(self, url: str) -> str:
        """Scrape a page for text data"""
        try:
            client = self._get_client()
            response = client.scrape_url(url,  params={'formats': ['markdown']})  
            logger.info(f"Successfully scraped page : {url}")    
            return response['markdown']     
        except Exception as e:
            raise FirecrawlAPIError(f"Scraping {url} failed: {e}")
        
          
    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Twitter action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)