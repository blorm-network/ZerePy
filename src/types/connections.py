from pydantic import Field, BaseModel
from typing import Optional, Dict, Any, List
from .config import BaseConnectionConfig, LLMConnectionConfig, BlockchainConnectionConfig

class OpenAIConfig(LLMConnectionConfig):
    """Configuration for OpenAI API connection.
    
    Example:
        {
            "name": "openai",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 1000,
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "openai"
        model: OpenAI model to use (e.g., "gpt-3.5-turbo", "gpt-4")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        api_key: OpenAI API key (optional if set in environment)
    """
    name: str = "openai"
    model: str = "gpt-3.5-turbo"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)

class AnthropicConfig(LLMConnectionConfig):
    """Configuration for Anthropic API connection.
    
    Example:
        {
            "name": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "anthropic"
        model: Anthropic model to use (e.g., "claude-3-5-sonnet-20241022")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        presence_penalty: Penalizes repeated presence of tokens (-2.0 to 2.0)
        frequency_penalty: Penalizes repeated frequency of tokens (-2.0 to 2.0)
        api_key: Anthropic API key (optional if set in environment)
    """
    name: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)

class SolanaConfig(BlockchainConnectionConfig):
    """Configuration for Solana blockchain connection.
    
    Example:
        {
            "name": "solana",
            "rpc": "https://api.mainnet-beta.solana.com",
            "network": "mainnet",
            "commitment": "confirmed",
            "timeout": 30
        }
    
    Fields:
        name: Connection identifier, must be "solana"
        rpc: Solana RPC endpoint URL
        network: Network to connect to (e.g., "mainnet", "devnet")
        commitment: Transaction commitment level ("processed", "confirmed", "finalized")
        timeout: Request timeout in seconds (default: 30)
    """
    name: str = "solana"
    commitment: str = "confirmed"
    timeout: int = Field(default=30, ge=1)
    
class EthereumConfig(BlockchainConnectionConfig):
    """Configuration for Ethereum blockchain connection.
    
    Example:
        {
            "name": "ethereum",
            "rpc": "https://eth-mainnet.g.alchemy.com/v2/your-api-key",
            "network": "mainnet",
            "chain_id": 1,
            "gas_limit": 500000
        }
    
    Fields:
        name: Connection identifier, must be "ethereum"
        rpc: Ethereum RPC endpoint URL
        network: Network to connect to (e.g., "mainnet", "goerli")
        chain_id: Network chain ID (optional, derived from network if not provided)
        gas_limit: Maximum gas limit for transactions (optional)
    """
    name: str = "ethereum"
    chain_id: Optional[int] = None
    gas_limit: Optional[int] = Field(default=None, gt=0)
    
class FarcasterConfig(BaseConnectionConfig):
    """Configuration for Farcaster social network connection.
    
    Example:
        {
            "name": "farcaster",
            "recovery_phrase": "your twelve word recovery phrase here",
            "endpoint": "https://api.farcaster.xyz",
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "farcaster"
        recovery_phrase: Farcaster wallet recovery phrase (optional if set in environment)
        endpoint: Custom API endpoint URL (optional)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "farcaster"
    recovery_phrase: Optional[str] = None
    endpoint: Optional[str] = None
    timeline_read_count: int = Field(default=100, gt=0)
    
class TwitterConfig(BaseConnectionConfig):
    """Configuration for Twitter/X social network connection.
    
    Example:
        {
            "name": "twitter",
            "api_key": "your-api-key",
            "api_secret": "your-api-secret",
            "access_token": "your-access-token",
            "access_token_secret": "your-access-token-secret",
            "timeline_read_count": 20,
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "twitter"
        api_key: Twitter API key
        api_secret: Twitter API secret
        access_token: OAuth access token (optional)
        access_token_secret: OAuth access token secret (optional)
        timeline_read_count: Number of tweets to fetch (default: 10)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "twitter"
    api_key: str
    api_secret: str
    access_token: Optional[str] = None
    access_token_secret: Optional[str] = None
    timeline_read_count: int = Field(default=10, gt=0)

class TogetherConfig(LLMConnectionConfig):
    """Configuration for Together AI LLM connection.
    
    Example:
        {
            "name": "together",
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "together"
        model: Together AI model to use (e.g., "mistralai/Mixtral-8x7B-Instruct-v0.1")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        api_key: Together AI API key (optional if set in environment)
    """
    name: str = "together"
    model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)

class OllamaConfig(LLMConnectionConfig):
    """Configuration for Ollama local LLM connection.
    
    Example:
        {
            "name": "ollama",
            "model": "mistral",
            "temperature": 0.7,
            "max_tokens": 2000,
            "host": "http://localhost:11434"
        }
    
    Fields:
        name: Connection identifier, must be "ollama"
        model: Ollama model to use (e.g., "mistral", "llama2")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        host: Ollama server URL (default: http://localhost:11434)
    """
    name: str = "ollama"
    model: str = "mistral"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    host: str = "http://localhost:11434"

class GroqConfig(LLMConnectionConfig):
    """Configuration for Groq LLM connection.
    
    Example:
        {
            "name": "groq",
            "model": "mixtral-8x7b-32768",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "groq"
        model: Groq model to use (e.g., "mixtral-8x7b-32768")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        api_key: Groq API key (optional if set in environment)
    """
    name: str = "groq"
    model: str = "mixtral-8x7b-32768"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    base_url: str = "https://api.groq.com/openai/v1"  # Groq's API endpoint

class EternalAIConfig(LLMConnectionConfig):
    """Configuration for EternalAI hybrid LLM/blockchain connection.
    
    Example:
        {
            "name": "eternalai",
            "model": "eternal-v1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "chain_id": "45762",
            "agent_id": 123,
            "contract_address": "0x1234...",
            "rpc_url": "https://rpc.eternal.ai",
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "eternalai"
        model: EternalAI model to use (e.g., "eternal-v1")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        chain_id: Blockchain network chain ID (default: "45762")
        agent_id: EternalAI agent ID (optional)
        contract_address: Smart contract address (optional)
        rpc_url: Custom RPC endpoint URL (optional)
        api_key: EternalAI API key (optional if set in environment)
    """
    name: str = "eternalai"
    model: str = "eternal-v1"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    chain_id: str = "45762"  # Default chain ID
    agent_id: Optional[int] = None
    contract_address: Optional[str] = None
    rpc_url: Optional[str] = None

class HyperbolicConfig(LLMConnectionConfig):
    """Configuration for Hyperbolic LLM connection.
    
    Example:
        {
            "name": "hyperbolic",
            "model": "hyperbolic-v1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "hyperbolic"
        model: Hyperbolic model to use (e.g., "hyperbolic-v1")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        presence_penalty: Penalizes repeated presence of tokens (-2.0 to 2.0)
        frequency_penalty: Penalizes repeated frequency of tokens (-2.0 to 2.0)
        api_key: Hyperbolic API key (optional if set in environment)
    """
    name: str = "hyperbolic"
    model: str = "hyperbolic-v1"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    base_url: str = "https://api.hyperbolic.xyz/v1"  # Hyperbolic's API endpoint

class PluginConfig(BaseModel):
    """Configuration for a Goat plugin.
    
    Example:
        {
            "name": "erc20",
            "args": {
                "contract_address": "0x1234...",
                "chain_id": 1,
                "decimals": 18
            }
        }
    
    Fields:
        name: Plugin identifier (e.g., "erc20", "coingecko")
        args: Plugin-specific configuration arguments
    """
    name: str
    args: Dict[str, Any]

class GoatConfig(BaseConnectionConfig):
    """Configuration for Goat plugin-based connection.
    
    Example:
        {
            "name": "goat",
            "plugins": [
                {
                    "name": "erc20",
                    "args": {
                        "contract_address": "0x1234...",
                        "chain_id": 1,
                        "decimals": 18
                    }
                },
                {
                    "name": "coingecko",
                    "args": {
                        "api_key": "your-api-key"
                    }
                }
            ],
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "goat"
        plugins: List of plugin configurations to enable
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "goat"
    plugins: List[PluginConfig]

class EchoChamberConfig(BaseConnectionConfig):
    """Configuration for EchoChamber social network connection.
    
    Example:
        {
            "name": "echochamber",
            "api_url": "https://api.echochamber.xyz",
            "api_key": "your-api-key",
            "room": "general",
            "sender_username": "bot_user",
            "sender_model": "gpt-4",
            "history_read_count": 100,
            "post_history_track": 50,
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "echochamber"
        api_url: EchoChamber API endpoint URL
        api_key: API key for authentication
        room: Chat room identifier
        sender_username: Username to post messages as
        sender_model: Model identifier for message generation
        history_read_count: Number of messages to fetch (default: 100)
        post_history_track: Number of messages to track (default: 50)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "echochamber"
    api_url: str
    api_key: str
    room: str
    sender_username: str
    sender_model: str
    history_read_count: int = Field(default=100, gt=0)
    post_history_track: int = Field(default=50, gt=0)

class SonicConfig(BlockchainConnectionConfig):
    """Configuration for Sonic DEX blockchain connection.
    
    Example:
        {
            "name": "sonic",
            "network": "mainnet",
            "rpc_url": "https://rpc.sonic.network",
            "explorer_url": "https://explorer.sonic.network",
            "aggregator_api": "https://aggregator-api.kyberswap.com/sonic/api/v1",
            "max_queue_size": 100,
            "gas_limit": 500000,
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "sonic"
        network: Network to connect to (e.g., "mainnet", "testnet")
        rpc_url: Custom RPC endpoint URL (optional, derived from network)
        explorer_url: Block explorer URL (optional, derived from network)
        aggregator_api: KyberSwap aggregator API endpoint
        max_queue_size: Maximum transaction queue size (default: 100)
        gas_limit: Maximum gas limit for transactions (optional)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "sonic"
    network: str = "mainnet"
    rpc_url: Optional[str] = None  # Optional since it can be derived from network
    explorer_url: Optional[str] = None  # Optional since it can be derived from network
    aggregator_api: str = "https://aggregator-api.kyberswap.com/sonic/api/v1"
    max_queue_size: int = Field(default=100, gt=0)
    gas_limit: Optional[int] = Field(default=None, gt=0)

class AlloraConfig(BlockchainConnectionConfig):
    """Configuration for Allora Network blockchain connection.
    
    Example:
        {
            "name": "allora",
            "rpc": "https://rpc.allora.network",
            "network": "mainnet",
            "chain_slug": "testnet",
            "api_url": "https://api.allora.network",
            "inference_timeout": 30,
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "allora"
        rpc: Allora RPC endpoint URL
        network: Network to connect to (e.g., "mainnet", "testnet")
        chain_slug: Chain identifier (default: "testnet")
        api_url: Custom API endpoint URL (optional)
        inference_timeout: Timeout for inference requests in seconds (default: 30)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "allora"
    chain_slug: str = "testnet"  # Default to testnet as per connection class
    api_url: Optional[str] = None
    inference_timeout: int = Field(default=30, gt=0)  # Timeout in seconds for inference requests

class XAIConfig(LLMConnectionConfig):
    """Configuration for XAI (x.ai) LLM connection.
    
    Example:
        {
            "name": "xai",
            "model": "grok-1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "base_url": "https://api.x.ai/v1",
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "xai"
        model: XAI model to use (e.g., "grok-1")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        presence_penalty: Penalizes repeated presence of tokens (-2.0 to 2.0)
        frequency_penalty: Penalizes repeated frequency of tokens (-2.0 to 2.0)
        base_url: XAI API endpoint URL (default: https://api.x.ai/v1)
        api_key: XAI API key (optional if set in environment)
    """
    name: str = "xai"
    model: str = "grok-1"  # Default model
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    base_url: str = "https://api.x.ai/v1"  # XAI's API endpoint

class GaladrielConfig(LLMConnectionConfig):
    """Configuration for Galadriel LLM connection with fine-tuning support.
    
    Example:
        {
            "name": "galadriel",
            "model": "galadriel-v1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "base_url": "https://api.galadriel.com/v1/verified",
            "fine_tune_api_key": "your-fine-tune-key",  # Optional, for fine-tuning only
            "api_key": "your-api-key"  # Optional, can be set via environment variable
        }
    
    Fields:
        name: Connection identifier, must be "galadriel"
        model: Galadriel model to use (e.g., "galadriel-v1")
        temperature: Controls randomness in responses (0.0 to 2.0)
        max_tokens: Maximum tokens in response (optional)
        top_p: Top-p sampling parameter (0.0 to 1.0)
        presence_penalty: Penalizes repeated presence of tokens (-2.0 to 2.0)
        frequency_penalty: Penalizes repeated frequency of tokens (-2.0 to 2.0)
        base_url: Galadriel API endpoint URL (default: https://api.galadriel.com/v1/verified)
        fine_tune_api_key: API key for fine-tuning operations (optional)
        api_key: Galadriel API key (optional if set in environment)
    """
    name: str = "galadriel"
    model: str = "galadriel-v1"  # Default model
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    base_url: str = "https://api.galadriel.com/v1/verified"  # Galadriel's API endpoint
    fine_tune_api_key: Optional[str] = None  # Optional fine-tune API key

class DiscordConfig(BaseConnectionConfig):
    """Configuration for Discord chat platform connection.
    
    Example:
        {
            "name": "discord",
            "bot_token": "your-bot-token",
            "guild_id": "123456789",  # Optional, specific server ID
            "channel_id": "987654321",  # Optional, specific channel ID
            "message_limit": 100,
            "message_interval": 60,
            "enabled": true
        }
    
    Fields:
        name: Connection identifier, must be "discord"
        bot_token: Discord bot token for authentication
        guild_id: Specific server/guild ID to connect to (optional)
        channel_id: Specific channel ID to monitor (optional)
        message_limit: Maximum messages to fetch per request (default: 100)
        message_interval: Time between message checks in seconds (default: 60)
        enabled: Whether the connection is enabled (default: true)
    """
    name: str = "discord"
    bot_token: str
    guild_id: Optional[str] = None
    channel_id: Optional[str] = None
    message_limit: int = Field(default=100, gt=0)
    message_interval: int = Field(default=60, gt=0)
