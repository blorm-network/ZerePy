import random
import time
import logging
import os
from dotenv import load_dotenv
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar
from src.action_handler import execute_action
import src.actions.twitter_actions
import src.actions.echochamber_actions
import src.actions.solana_actions
from datetime import datetime

logger = logging.getLogger("agent")

class LegacyZerePyAgent:
    def __init__(self, agent_config: dict):
        try:
            # Load agent configuration
            self._setup_agent_config(agent_config)

            self.is_llm_set = False

            # Set up empty agent state
            self.context = {}

        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise e

    def _setup_agent_config(self, agent_config: dict):
        try:
            # GENERAL CONFIG
            general_config = agent_config["config"]
            self.name = general_config["name"]
            self.loop_delay = general_config["loop_delay"]
            self.time_based_multipliers = general_config.get("time_based_multipliers", None)

            # CONNECTIONS
            connections_config = agent_config["connections"]
            self.connection_manager = ConnectionManager(connections_config)

            # LLM CONFIG
            llm_config = agent_config["llms"]
            character_config = llm_config["character"]
            self.character_name = character_config["name"]
            self.bio = character_config.get("bio", [])
            self.traits = character_config.get("traits", [])
            self.examples = character_config.get("examples", [])
            self.example_accounts = character_config.get("example_accounts", [])
            self.model_provider = character_config["model_provider"]
            self.model = character_config["model"]

            # SYSTEM PROMPT
            self._system_prompt = None
            self._system_prompt = self._construct_system_prompt()

            # TASK CONFIGS
            self.tasks = agent_config.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]

            # TWITTER CONFIG
            # TODO: None of this does anything! These values are set and never used!
            has_twitter_tasks = any("tweet" in task["name"] for task in self.tasks)
            twitter_config = next((config for config in connections_config if config["name"] == "twitter"), None)

            if has_twitter_tasks and twitter_config:
                self.tweet_interval = twitter_config["config"].get("tweet_interval", 900)
                self.own_tweet_replies_count = twitter_config["config"].get("own_tweet_replies_count", 2)
                # Get the username from the .env file to avoid self reply
                load_dotenv()
                self.username = os.getenv('TWITTER_USERNAME', '').lower()
                if not self.username:
                    logger.warning("Twitter username not found, some Twitter functionalities may be limited")

            # ECHOCAMBERS CONFIG
            echochambers_config = next((config for config in connections_config if config["name"] == "echochambers"), None)
            if echochambers_config:
                self.echochambers_message_interval = echochambers_config["config"].get("message_interval", 60)
                self.echochambers_history_count = echochambers_config["config"].get("history_read_count", 50)

        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise e

    def _setup_llm_provider(self):
        # Get first available LLM provider and its model
        llm_providers = self.connection_manager.get_model_providers()
        if not llm_providers:
            raise ValueError("No configured LLM provider found")
        self.model_provider = llm_providers[0]

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)

            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples or self.example_accounts:
                prompt_parts.append("\nHere are some examples of your style (Please avoid repeating any of these):")
                if self.examples:
                    prompt_parts.extend(f"- {example}" for example in self.examples)

                if self.example_accounts:
                    for example_account in self.example_accounts:
                        tweets = self.connection_manager.perform_action(
                            connection_name="twitter",
                            action_name="get-latest-tweets-from-user",
                            params=[example_account]
                        )
                        if tweets:
                            prompt_parts.extend(f"- {tweet['text']}" for tweet in tweets)

            self._system_prompt = "\n".join(prompt_parts)

        return self._system_prompt

    def _adjust_weights_for_time(self, current_hour: int, task_weights: list) -> list:
        weights = task_weights.copy()

        # Reduce tweet frequency during night hours (1 AM - 5 AM)
        if 1 <= current_hour <= 5:
            weights = [
                weight * self.time_based_multipliers.get("tweet_night_multiplier", 0.4) if task["name"] == "post-tweet"
                else weight
                for weight, task in zip(weights, self.tasks)
            ]

        # Increase engagement frequency during day hours (8 AM - 8 PM) (peak hours?🤔)
        if 8 <= current_hour <= 20:
            weights = [
                weight * self.time_based_multipliers.get("engagement_day_multiplier", 1.5) if task["name"] in ("reply-to-tweet", "like-tweet")
                else weight
                for weight, task in zip(weights, self.tasks)
            ]

        return weights

    def prompt_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using the configured LLM provider"""
        system_prompt = system_prompt or self._construct_system_prompt()

        return self.connection_manager.perform_action(
            connection_name=self.model_provider,
            action_name="generate-text",
            params=[prompt, system_prompt]
        )

    def perform_action(self, connection: str, action: str, **kwargs) -> None:
        return self.connection_manager.perform_action(connection, action, **kwargs)

    def select_action(self) -> dict:
        task_weights = [weight for weight in self.task_weights.copy()]

        if self.time_based_multipliers:
            current_hour = datetime.now().hour
            task_weights = self._adjust_weights_for_time(current_hour, task_weights)

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
                success = False
                try:
                    # REPLENISH INPUTS
                    if "timeline_tweets" not in self.context or self.context["timeline_tweets"] is None or len(self.context["timeline_tweets"]) == 0:
                        if any("tweet" in task["name"] for task in self.tasks):
                            logger.info("\n👀 READING TIMELINE")
                            self.context["timeline_tweets"] = self.connection_manager.perform_action(
                                connection_name="twitter",
                                action_name="read-timeline",
                                params=[]
                            )

                    if "room_info" not in self.context or self.context["room_info"] is None:
                        if any("echochambers" in task["name"] for task in self.tasks):
                            logger.info("\n👀 READING ECHOCHAMBERS ROOM INFO")
                            self.context["room_info"] = self.connection_manager.perform_action(
                                connection_name="echochambers",
                                action_name="get-room-info",
                                params={}
                            )

                    # CHOOSE AN ACTION
                    action = self.select_action()
                    action_name = action["name"]

                    # PERFORM ACTION
                    success = execute_action(self, action_name)

                    logger.info(f"\n⏳ Waiting {self.loop_delay} seconds before next loop...")
                    print_h_bar()
                    time.sleep(self.loop_delay if success else 60)

                except Exception as e:
                    logger.error(f"\n❌ Error in agent loop iteration: {e}")
                    logger.info(f"⏳ Waiting {self.loop_delay} seconds before retrying...")
                    time.sleep(self.loop_delay)

        except KeyboardInterrupt:
            logger.info("\n🛑 Agent loop stopped by user.")
            return