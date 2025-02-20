import json
import random
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar
from src.action_handler import execute_action
import src.actions.twitter_actions
import src.actions.echochamber_actions
import src.actions.solana_actions
from datetime import datetime

REQUIRED_FIELDS = ["name", "bio", "traits",
                   "examples", "loop_delay", "config", "tasks"]

logger = logging.getLogger("agent")


class ZerePyAgent:
    def __init__(
            self,
            agent_name: str
    ):
        try:
            agent_path = Path("agents") / f"{agent_name}.json"
            # Modified to explicitly use UTF-8 encoding
            with open(agent_path, "r", encoding='utf-8') as f:
                agent_dict = json.load(f)

            missing_fields = [
                field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(
                    f"Missing required fields: {', '.join(missing_fields)}")

            self.name = agent_dict["name"]
            self.bio = agent_dict["bio"]
            self.traits = agent_dict["traits"]
            self.examples = agent_dict["examples"]
            self.example_accounts = agent_dict.get(
                "example_accounts", [])  # Made optional with default
            self.loop_delay = agent_dict["loop_delay"]
            self.connection_manager = ConnectionManager(agent_dict["config"])
            self.use_time_based_weights = agent_dict.get(
                "use_time_based_weights", False)  # Made optional with default
            self.time_based_multipliers = agent_dict.get(
                "time_based_multipliers", {})  # Made optional with default

            has_twitter_tasks = any(
                "tweet" in task["name"] for task in agent_dict.get("tasks", []))

            twitter_config = next(
                (config for config in agent_dict["config"] if config["name"] == "twitter"), None)

            if has_twitter_tasks and twitter_config:
                self.tweet_interval = twitter_config.get("tweet_interval", 900)
                self.own_tweet_replies_count = twitter_config.get(
                    "own_tweet_replies_count", 2)

            # Extract Echochambers config
            echochambers_config = next(
                (config for config in agent_dict["config"] if config["name"] == "echochambers"), None)
            if echochambers_config:
                self.echochambers_message_interval = echochambers_config.get(
                    "message_interval", 60)
                self.echochambers_history_count = echochambers_config.get(
                    "history_read_count", 50)

            self.is_llm_set = False

            # Cache for system prompt
            self._system_prompt = None

            # Extract loop tasks
            self.tasks = agent_dict.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]
            self.logger = logging.getLogger("agent")

            # Set up empty agent state
            self.state = {}

        except FileNotFoundError:
            logger.error(f"Agent file not found: {agent_name}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in agent file: {e}")
            raise
        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise

    def _setup_llm_provider(self):
        """Set up the language model provider for the agent"""
        # Get first available LLM provider and its model
        llm_providers = self.connection_manager.get_model_providers()
        if not llm_providers:
            raise ValueError("No configured LLM provider found")
        self.model_provider = llm_providers[0]

        # Load Twitter username for self-reply detection if Twitter tasks exist
        if any("tweet" in task["name"] for task in self.tasks):
            load_dotenv()
            self.username = os.getenv('TWITTER_USERNAME', '').lower()
            if not self.username:
                logger.warning(
                    "Twitter username not found, some Twitter functionalities may be limited")

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)

            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples or self.example_accounts:
                prompt_parts.append(
                    "\nHere are some examples of your style (Please avoid repeating any of these):")
                if self.examples:
                    prompt_parts.extend(
                        f"- {example}" for example in self.examples)

                if self.example_accounts:
                    for example_account in self.example_accounts:
                        tweets = self.connection_manager.perform_action(
                            connection_name="twitter",
                            action_name="get-latest-tweets",
                            params=[example_account]
                        )
                        if tweets:
                            prompt_parts.extend(
                                f"- {tweet['text']}" for tweet in tweets)

            self._system_prompt = "\n".join(prompt_parts)

        return self._system_prompt

    def _adjust_weights_for_time(self, current_hour: int, task_weights: list) -> list:
        """Adjust task weights based on the current time of day"""
        weights = task_weights.copy()

        # Reduce tweet frequency during night hours (1 AM - 5 AM)
        if 1 <= current_hour <= 5:
            weights = [
                weight * self.time_based_multipliers.get("tweet_night_multiplier", 0.4) if task["name"] == "post-tweet"
                else weight
                for weight, task in zip(weights, self.tasks)
            ]

        # Increase engagement frequency during day hours (8 AM - 8 PM)
        if 8 <= current_hour <= 20:
            weights = [
                weight * self.time_based_multipliers.get("engagement_day_multiplier", 1.5) if task["name"] in ("reply-to-tweet", "like-tweet")
                else weight
                for weight, task in zip(weights, self.tasks)
            ]

        return weights

    def prompt_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using the configured LLM provider"""
        if not self.is_llm_set:
            self._setup_llm_provider()

        system_prompt = system_prompt or self._construct_system_prompt()

        return self.connection_manager.perform_action(
            connection_name=self.model_provider,
            action_name="generate-text",
            params=[prompt, system_prompt]
        )

    def perform_action(self, connection: str, action: str, params: list = None) -> any:
        """Perform a specific action using the connection manager"""
        if params is None:
            params = []
        return self.connection_manager.perform_action(connection, action, params)

    def select_action(self, use_time_based_weights: bool = False) -> dict:
        """Select an action based on weights and time-based adjustments"""
        task_weights = self.task_weights.copy()

        if use_time_based_weights:
            current_hour = datetime.now().hour
            task_weights = self._adjust_weights_for_time(
                current_hour, task_weights)

        return random.choices(self.tasks, weights=task_weights, k=1)[0]

    def loop(self):
        """Main agent loop for autonomous behavior"""
        if not self.is_llm_set:
            self._setup_llm_provider()

        logger.info("\n🚀 Starting agent loop...")
        logger.info("Press Ctrl+C at any time to stop the loop.")
        print_h_bar()

        time.sleep(2)
        logger.info("Starting loop in 5 seconds...")
        for i in range(5, 0, -1):
            logger.info(f"{i}...")
            time.sleep(1)

        try:
            while True:
                try:
                    # Replenish inputs
                    if "timeline_tweets" not in self.state or not self.state["timeline_tweets"]:
                        if any("tweet" in task["name"] for task in self.tasks):
                            logger.info("\n👀 READING TIMELINE")
                            self.state["timeline_tweets"] = self.connection_manager.perform_action(
                                connection_name="twitter",
                                action_name="read-timeline",
                                params=[]
                            )

                    if "room_info" not in self.state or not self.state["room_info"]:
                        if any("echochambers" in task["name"] for task in self.tasks):
                            logger.info("\n👀 READING ECHOCHAMBERS ROOM INFO")
                            self.state["room_info"] = self.connection_manager.perform_action(
                                connection_name="echochambers",
                                action_name="get-room-info",
                                params={}
                            )

                    # Choose and execute action
                    action = self.select_action(
                        use_time_based_weights=self.use_time_based_weights)
                    action_name = action["name"]
                    success = execute_action(self, action_name)

                    logger.info(
                        f"\n⏳ Waiting {self.loop_delay} seconds before next loop...")
                    print_h_bar()
                    time.sleep(self.loop_delay if success else 60)

                except Exception as e:
                    logger.error(f"\n❌ Error in agent loop iteration: {e}")
                    logger.info(
                        f"⏳ Waiting {self.loop_delay} seconds before retrying...")
                    time.sleep(self.loop_delay)

        except KeyboardInterrupt:
            logger.info("\n🛑 Agent loop stopped by user.")
            return

    def __str__(self) -> str:
        """String representation of the agent"""
        return f"ZerePyAgent(name='{self.name}')"

    def __repr__(self) -> str:
        """Detailed string representation of the agent"""
        return f"ZerePyAgent(name='{self.name}', tasks={len(self.tasks)}, llm_set={self.is_llm_set})"
