import logging
from typing import Dict, Any
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from goat_adapters.langchain import get_on_chain_tools
from web3 import Web3
from web3.middleware.signing import construct_sign_and_send_raw_middleware
from eth_account import Account
from goat_wallets.web3 import Web3EVMWalletClient
from goat_wallets.evm import send_eth  
from goat_plugins.erc20.token import PEPE, USDC
from goat_plugins.erc20 import ERC20PluginOptions, erc20
from goat_plugins.coingecko import CoinGeckoPluginOptions, coingecko
from goat_plugins.uniswap import UniswapPluginOptions, uniswap
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from goat_plugins.dexscreener import dexscreener, DexscreenerPluginOptions
import os
from dotenv import load_dotenv

logger = logging.getLogger("connections.brain_connection")

class BrainConnectionError(Exception):
    """Base exception for Brain connection errors"""
    pass

SYSTEM_PROMPT = """You are Blormmy, an advanced onchain assistant that combines educational expertise with direct transaction capabilities. You serve two core functions:

1. TRANSACTION CAPABILITIES:
    - Execute token swaps through Uniswap, but taking an intial dexscreener step to verify addresses if presented with tickers
    - Process token transfers
    - Look up token information and prices
    - NOTE: for all transactions, ensure tx hash is visible in the final result message

2. EDUCATIONAL SUPPORT:
    - Explain crypto concepts and terminology
    - Guide users through understanding DeFi mechanics
    - Answer questions about blockchain technology

CORE TRANSACTION RULES:
1. For any swap operation:
    - ALWAYS use dexscreener plugin to verify token addresses first, regardless of input format
    - Ensure token addresses match the currently connected network
    - Get a quote using uniswap_get_quote
    - Execute swap using uniswap_swap_tokens with EXACTLY the same parameters
    - Use base units (wei) for all amounts (e.g., 1 WETH = 1000000000000000000)
    - Skip approval checks as they're handled automatically

2. For token operations:
    - MANDATORY: Use dexscreener plugin to look up ALL token addresses, even for common tokens
    - Verify token contract addresses match the current network before any operation
    - Never use hardcoded addresses or assume token contracts across networks
    - Use small amounts for testing purposes
    - Never ask for transaction verification - execute directly

3. Plugin Usage Rules:
    - dexscreener plugin MUST be used first for ANY token interaction
    - Only perform actions available through loaded plugins
    - If a requested action isn't available, clearly state that it's not possible
    - Always verify network compatibility of retrieved addresses

RESPONSE PROTOCOL:
1. For transaction requests:
    - Verify token addresses via dexscreener for current network
    - Execute without asking for confirmation
    - Provide clear transaction details
    - Report success/failure status
    - <CRITICAL> NEVER USE get_token_by_symbol action from the erc20 plugin. </CRITICAL>
    - always pass the amount as an integer and not a string, or else the transaction will fail

2. For educational queries:
    - Provide clear, accurate information
    - Use real examples when relevant
    - Break down complex concepts step by step

DONT SAY YOU CANT FIND A TOKEN IF YOU DIDNT LOOK IT UP ON dexscreener. THEN JUST FIND THE ADDRESS FOR THE CURRENT CHAIN AND DONT
CALL THE GET_TOKEN_INFO_BY_SYMBOL thing from ERC20. EXTRACT CONTRACT ADDRESS FROM dexscreener CALL AND USE DIRECTLY FOR SEND/SWAP

Never execute transactions outside of plugin capabilities or suggest unofficial alternatives. Always verify token addresses through dexscreener and ensure network compatibility before any operation. Maintain a balance between being informative and action-oriented, always prioritizing user security and accurate execution of requests."""

@dataclass
class ChatHistory:
    """Storage for chat context"""
    messages: list[dict[str, str]] = None

    def __post_init__(self):
        self.messages = [] if self.messages is None else self.messages

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def to_langchain_messages(self):
        return [
            (SystemMessage if msg["role"] == "system" else 
             HumanMessage if msg["role"] == "human" else 
             AIMessage)(content=msg["content"])
            for msg in self.messages
            if msg["role"] in ("system", "human", "ai")
        ]

class BrainConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        self.provider = None
        self.model = None
        self.agent_executor = None
        self.chat_history = ChatHistory()
        self._wallet_client = None
        self.llm = None
        super().__init__(config)
        
    def _initialize_web3(self):
        """Initialize Web3 with configuration"""
        load_dotenv()
        rpc_url = os.getenv("GOAT_RPC_PROVIDER_URL")
        private_key = os.getenv("GOAT_WALLET_PRIVATE_KEY")
        
        if not rpc_url or not private_key:
            raise BrainConnectionError("Missing RPC URL or private key in environment")
            
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise BrainConnectionError("Failed to connect to RPC provider")
            
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        
        account = Account.from_key(private_key)
        w3.eth.default_account = account.address
        w3.eth.default_local_account = account
        w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))
        
        return Web3EVMWalletClient(w3)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Brain configuration"""
        required_fields = ["provider", "model"]
        missing = [f for f in required_fields if f not in config]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
            
        if config["provider"] not in ["anthropic", "openai"]:
            raise ValueError("Provider must be either 'anthropic' or 'openai'")
            
        return config

    def register_actions(self) -> None:
        """Register available Brain actions"""
        self.actions = {
            "process-command": Action(
                name="process-command",
                parameters=[
                    ActionParameter("command", True, str, "Natural language command to process")
                ],
                description="Process natural language into blockchain action"
            )
        }
        
    def _setup_llm(self) -> None:
        """Initialize the LLM based on configuration"""
        if self.config["provider"] == "anthropic":
            self.llm = ChatAnthropic(model=self.config["model"])
        else:  # openai
            self.llm = ChatOpenAI(model=self.config["model"])

    def _setup_langchain_agent(self) -> None:
        """Initialize Langchain agent with hardcoded GOAT plugins"""
        try:
            # Create chatbot prompt template
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}")
            ])

            # Initialize plugins with default configurations
            plugins = [
                erc20(options=ERC20PluginOptions(tokens=[USDC, PEPE])),
                coingecko(options=CoinGeckoPluginOptions(api_key=os.getenv("COINGECKO_KEY"))),
                uniswap(options=UniswapPluginOptions(
                    api_key=os.getenv("UNISWAP_API_KEY"),
                    base_url=os.getenv("UNISWAP_BASE_URL")
                )),
                dexscreener(DexscreenerPluginOptions()),
                send_eth()
            ]

            # Get tools using the wallet client and plugins
            tools = get_on_chain_tools(
                wallet=self._wallet_client,
                plugins=plugins
            )

            # Create agent and executor
            agent = create_tool_calling_agent(self.llm, tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                handle_parsing_errors=True,
                verbose=True
            )
            
        except Exception as e:
            raise BrainConnectionError(f"Agent setup failed: {str(e)}")

    def configure(self) -> bool:
        """Configure the brain connection"""
        try:
            # Initialize Web3 and wallet
            self._wallet_client = self._initialize_web3()
            
            # Setup LLM and agent
            self._setup_llm()
            self._setup_langchain_agent()
            return True
                
        except Exception as e:
            logger.error(f"Brain configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        configured = (
            self.llm is not None and 
            self.agent_executor is not None and
            self._wallet_client is not None
        )
        
        if verbose and not configured:
            if not self.llm:
                logger.error("LLM not initialized")
            if not self.agent_executor:
                logger.error("Langchain agent not initialized")
            if not self._wallet_client:
                logger.error("Web3 wallet not initialized")
        return configured

    def process_command(self, command: str) -> str:
        """Process a natural language command"""
        if not self.is_configured(verbose=True):
            return "Brain connection not fully configured"

        try:
            self.chat_history.add_message("human", command)
            response = self.agent_executor.invoke({
                "input": command,
                "chat_history": self.chat_history.to_langchain_messages()
            })
            
            output = response["output"]
            self.chat_history.add_message("ai", output)
            return output

        except Exception as e:
            error_msg = str(e)
            # if "'HexBytes' object has no attribute 'to_0x_hex'" in error_msg:
            #     return "hexbytes bug message but maybe went through"
            return f"Error processing command: {str(e)}"

    def perform_action(self, action_name: str, kwargs: Dict[str, Any]) -> Any:
        """Execute a brain action"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        if not self.is_configured(verbose=True):
            raise BrainConnectionError("Brain connection not configured")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method = getattr(self, action_name.replace("-", "_"))
        return method(**kwargs)