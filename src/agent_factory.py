import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, PositiveInt
from src.agent import ZerePyAgent
from src.legacy_agent import LegacyZerePyAgent

class AgentType(Enum):
    AUTONOMOUS = "autonomous"
    LEGACY = "legacy"

class GeneralConfig(BaseModel):
    name: str
    type: AgentType
    loop_delay: PositiveInt
    time_based_multipliers: Optional[Dict[str, float]] = None

class CharacterLLMConfig(BaseModel):
    name: str
    bio: Optional[List[str]] = []
    traits: Optional[List[str]] = []
    examples: Optional[List[str]] = []
    example_accounts: Optional[List[str]] = []
    model_provider: str
    model: str

class ExecutorLLMConfig(BaseModel):
    model_provider: str
    model: str

class LLMConfig(BaseModel):
    character: CharacterLLMConfig
    executor: Optional[ExecutorLLMConfig] = None

class ConnectionConfig(BaseModel):
    name: str
    config: Dict[str, Any]

class TaskConfig(BaseModel):
    name: str
    weight: PositiveInt


class AgentConfig(BaseModel):
    config: GeneralConfig
    llms: LLMConfig
    connections: List[ConnectionConfig]
    tasks: Optional[List[TaskConfig]] = []


class AgentFactory:
    @staticmethod
    def load_config(file_path: str) -> AgentConfig:
        """Loads the agent configuration from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            config = AgentConfig(**data)

            return config

        except FileNotFoundError:
            raise FileNotFoundError(f"Agent configuration file not found: {file_path}")
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid configuration file: {e}")

    @staticmethod
    def load_agent(file_path: str) -> ZerePyAgent:
        # Load the agent configuration
        agent_config = AgentFactory.load_config(file_path)

        # TODO: DO ANY ADDITIONAL VALIDATION ON CONFIG

        # Check Agent type
        if agent_config.config.type == AgentType.AUTONOMOUS:
            if agent_config.llms.executor is None:
                raise ValueError("Executor LLM is required for autonomous agents.")
            agent = ZerePyAgent(agent_config.model_dump())
        elif agent_config.config.type == AgentType.LEGACY:
            agent = LegacyZerePyAgent(agent_config.model_dump())
        else:
            raise ValueError(f"Invalid agent type: {agent_config.config.type}")

        return agent