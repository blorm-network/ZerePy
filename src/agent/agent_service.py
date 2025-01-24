from typing import List
from nest.core import Injectable


import logging

from src.lib.agent_config import AgentConfig
from src.lib.base_config import BASE_CONFIG, BaseConfig, AgentName

logger = logging.getLogger(__name__)


@Injectable
class AgentService:
    cfg: BaseConfig = BASE_CONFIG

    def get_config(self, agent_name: AgentName) -> AgentConfig:
        return self.cfg.agents[agent_name]

    def get_agents(self) -> List[AgentName]:
        return list(self.cfg.agents.keys())

    def get_connections(self, agent_name: AgentName) -> list[str]:
        cfg = self.get_config(agent_name)
        return cfg.list_connections()
