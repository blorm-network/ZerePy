from pydantic import BaseModel

from .twitter import TwitterConfig
from .solana import SolanaConfig
from .allora import AlloraConfig
from typing import Optional


class ConnectionsConfig(BaseModel):
    twitter: Optional[TwitterConfig]
    solana: Optional[SolanaConfig]
    allora: Optional[AlloraConfig]
