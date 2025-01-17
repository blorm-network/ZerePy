import logging
import os
import json
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from web3 import Web3
import requests

logger = logging.getLogger("connections.eternalai_connection")
IPFS = "ipfs://"
LIGHTHOUSE_IPFS = "https://gateway.lighthouse.storage/ipfs/"
GCS_ETERNAL_AI_BASE_URL = "https://cdn.eternalai.org/upload/"
AGENT_CONTRACT_ABI = [{"inputs": [{"internalType": "uint256","name": "_agentId","type": "uint256"}],"name": "getAgentSystemPrompt","outputs": [{"internalType": "bytes[]","name": "","type": "bytes[]"}],"stateMutability": "view","type": "function"}]

class EternalAIConnectionError(Exception):
    """Base exception for EternalAI connection errors"""
    pass


class EternalAIConfigurationError(EternalAIConnectionError):
    """Raised when there are configuration/credential issues"""
    pass


class EternalAIAPIError(EternalAIConnectionError):
    """Raised when EternalAI API requests fail"""
    pass


class EternalAIConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate EternalAI configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available EternalAI actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation")
                ],
                description="Generate text using EternalAI models"
            ),
            "check-model": Action(
                name="check-model",
                parameters=[
                    ActionParameter("model", True, str, "Model name to check availability")
                ],
                description="Check if a specific model is available"
            ),
            "list-models": Action(
                name="list-models",
                parameters=[],
                description="List all available EternalAI models"
            )
        }

    def _get_client(self) -> OpenAI:
        """Get or create EternalAI client"""
        if not self._client:
            api_key = os.getenv("EternalAI_API_KEY")
            api_url = os.getenv("EternalAI_API_URL")
            if not api_key or not api_url:
                raise EternalAIConfigurationError("EternalAI credentials not found in environment")
            self._client = OpenAI(api_key=api_key, base_url=api_url)
        return self._client

    def configure(self) -> bool:
        """Sets up EternalAI API authentication"""
        logger.info("\n🤖 EternalAI API SETUP")

        if self.is_configured():
            logger.info("\nEternalAI API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your EternalAI credentials:")
        logger.info("1. Visit https://eternalai.org/api")
        logger.info("2. Generate an API Key")
        logger.info("3. Use API url as https://api.eternalai.org/v1/")

        api_key = input("\nEnter your EternalAI API key: ")
        api_url = input("\nEnter your EternalAI API url: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'EternalAI_API_KEY', api_key)
            set_key('.env', 'EternalAI_API_URL', api_url)

            # Validate credentials
            client = OpenAI(api_key=api_key, base_url=api_url)
            client.models.list()

            logger.info("\n✅ EternalAI API configuration successfully saved!")
            logger.info("Your credentials have been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        """Check if EternalAI API credentials are configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('EternalAI_API_KEY')
            api_url = os.getenv('EternalAI_API_URL')
            if not api_key or not api_url:
                return False

            client = OpenAI(api_key=api_key, base_url=api_url)
            client.models.list()
            return True

        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    @staticmethod
    def get_on_chain_system_prompt_content(on_chain_data: str) -> str:
        if IPFS in on_chain_data:
            light_house = on_chain_data.replace(IPFS, LIGHTHOUSE_IPFS)
            response = requests.get(light_house)
            if response.status_code == 200:
                return response.text
            else:
                gcs = on_chain_data.replace(IPFS, GCS_ETERNAL_AI_BASE_URL)
                response = requests.get(gcs)
                if response.status_code == 200:
                    return response.text
                else:
                    raise Exception(f"invalid on-chain system prompt response status{response.status_code}")
        else:
            if len(on_chain_data) > 0:
                return on_chain_data
            else:
                raise Exception(f"invalid on-chain system prompt")

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, chain_id: str = None, **kwargs) -> str:
        """Generate text using EternalAI models"""
        try:
            client = self._get_client()
            model = model or self.config["model"]
            logger.info(f"model {model}")

            chain_id = chain_id or self.config["chain_id"]
            if not chain_id or chain_id == "":
                chain_id = "45762"
            logger.info(f"chain_id {chain_id}")

            agent_id = self.config["agent_id"] or None
            contract_address = self.config["contract_address"] or None
            rpc = self.config["rpc_url"] or None

            if agent_id and contract_address and rpc:
                logger.info(f"agent_id: {agent_id}, contract_address: {contract_address}")
                # call on-chain system prompt
                web3 = Web3(Web3.HTTPProvider(rpc))
                logger.info(f"web3 connected to {rpc} {web3.is_connected()}")
                contract = web3.eth.contract(address=contract_address, abi=AGENT_CONTRACT_ABI)
                result = contract.functions.getAgentSystemPrompt(agent_id).call()
                logger.info(f"on-chain system_prompt: {result}")
                if len(result) > 0:
                    try:
                        system_prompt = self.get_on_chain_system_prompt_content(result[0].decode("utf-8"))
                        logging.info(f"new system_prompt: {system_prompt}")
                    except Exception as e:
                        logger.error(f"get on-chain system_prompt fail {e}")

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                extra_body={"chain_id": chain_id}
            )

            if completion.choices is None:
                raise EternalAIAPIError(f"Text generation failed: completion.choices is None")
            try:
                if completion.onchain_data is not None:
                    logger.info(f"response onchain data: {json.dumps(completion.onchain_data, indent=4)}")
            except:
                logger.info(f"response onchain data object: {completion.onchain_data}", )
            return completion.choices[0].message.content

        except Exception as e:
            raise EternalAIAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
        """Check if a specific model is available"""
        try:
            client = self._get_client()
            try:
                client.models.retrieve(model=model)
                return True
            except Exception:
                return False
        except Exception as e:
            raise EternalAIAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs) -> None:
        """List all available EternalAI models"""
        try:
            client = self._get_client()
            response = client.models.list().data

            # Filter for fine-tuned models
            fine_tuned_models = [
                model for model in response
                if model.owned_by in ["organization", "user", "organization-owner"]
            ]

            if fine_tuned_models:
                logger.info("\nFINE-TUNED MODELS:")
                for i, model in enumerate(fine_tuned_models):
                    logger.info(f"{i + 1}. {model.id}")

        except Exception as e:
            raise EternalAIAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
