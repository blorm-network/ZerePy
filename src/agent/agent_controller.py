import json
import logging
from click import Parameter
import click
from nest.core.decorators.cli.cli_decorators import CliController, CliCommand
from .agent_service import AgentService
from src.lib.base_config import AgentName


class CommandOptions:
    AGENT = click.Option(
        ["-a", "--agent"], help="Agent to use", required=True, type=AgentName
    )
    CONNECTION = click.Option(
        ["-c", "--connection"], help="Connection to use", required=True, type=str
    )


@CliController("agent")
class AgentController:
    def __init__(self, agent_service: AgentService) -> None:
        self.agent_service: AgentService = agent_service

    @CliCommand("get-config")
    def config(self, agent: CommandOptions.AGENT) -> None:  # type: ignore
        res = self.agent_service.get_config(agent)
        # pretty print with indent=4
        logging.info(f"Result: {json.dumps(res, indent=2)}")

    # TODO: agent loop
    # TODO: chat
    # TODO: create
    # TODO: set-default
