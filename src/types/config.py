"""Configuration models for ZerePy connections.

Example configurations:

LLM Connection Example:
```python
{
    "name": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 1000
}
```

Blockchain Connection Example:
```python
{
    "name": "ethereum",
    "network": "mainnet",
    "rpc": "https://eth-mainnet.g.alchemy.com/v2/your-api-key",
    "gas_limit": 500000
}
```

Social Connection Example:
```python
{
    "name": "twitter",
    "api_key": "your-api-key",
    "api_secret": "your-api-secret",
    "timeline_read_count": 20
}
```
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class BaseConnectionConfig(BaseModel):
    """Base configuration model for all connections"""
    name: str
    enabled: bool = True
    
class LLMConnectionConfig(BaseConnectionConfig):
    """Configuration for LLM-based connections"""
    model: str
    api_key: Optional[str] = None
    
class BlockchainConnectionConfig(BaseConnectionConfig):
    """Configuration for blockchain connections"""
    rpc: str
    network: Optional[str] = "mainnet"
    
    class Config:
        # Allow extra fields for blockchain-specific configurations
        extra = "allow"
