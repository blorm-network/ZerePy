from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AgentConfig(BaseModel):
    """Configuration model for agents"""
    name: str = Field(..., description="Name of the agent")
    bio: List[str] = Field(..., description="List of biographical details about the agent")
    traits: List[str] = Field(..., description="List of personality traits and characteristics")
    examples: List[str] = Field(..., description="List of example behaviors and actions")
    example_accounts: List[str] = Field(..., description="List of example accounts to learn from")
    loop_delay: int = Field(default=60, gt=0, description="Delay between agent action loops in seconds")
    config: List[Dict[str, Any]] = Field(default_factory=list, description="List of additional configuration options")
    
    class Config:
        extra = "allow"  # Allow extra fields for backward compatibility
