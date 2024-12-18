import json
import random
import time
import logging
from src.connection_manager import ConnectionManager

logger = logging.getLogger("agent")

class ZerePyAgent:
    def __init__(
            self,
            name: str,
            display_name: str,
            model: str,
            model_provider: str,
            connection_manager: ConnectionManager,
            bio: str,
            traits: list[str],
            examples: list[str],
            timeline_read_count: int=10,
            replies_per_tweet: int=5,
            loop_delay: int=30
    ):
        self.name = name
        self.display_name = display_name
        self.model = model
        self.model_provider = model_provider
        self.connection_manager = connection_manager
        self.bio = bio
        self.traits = traits
        self.examples = examples

        # Behavior Parameters
        self.timeline_read_count = timeline_read_count
        self.replies_per_tweet = replies_per_tweet
        self.loop_delay = loop_delay


    def loop(self):
        # INITIAL DELAY
        time.sleep(2)
        print("Starting loop in 5 seconds...")
        for i in range(5):
            print(f"{i+1}...")
            time.sleep(2)

        # Main Loop
        while True:
            # READ TIMELINE AND REPLY
            print("\nREAD TWITTER TIMELINE")
            timeline_tweets = self.connection_manager.find_and_perform_action(
                action_string="read-timeline",
                connection_string="twitter",
                **{"count": self.timeline_read_count})
            for x, tweet in enumerate(timeline_tweets):
                # INTERACT WITH TWEET
                print("> INTERACT WITH TWEET:", tweet)
                action = random.choice([0, 1, 2])
                match action:
                    case 0:
                        print("-> LIKE TWEET")
                    case 1:
                        print("-> RETWEET TWEET")
                    case 2:
                        print("-> REPLY TO TWEET")

                # POST EVERY X INTERACTIONS
                if x % self.replies_per_tweet == 0:
                    print("-> POST ORIGINAL TWEET")

            # LOOP DELAY
            print(f"Delaying for {self.loop_delay} seconds...")
            time.sleep(self.loop_delay)

    def perform_action(self, action_string: str, connection_string: str, **kwargs):
            result = self.connection_manager.find_and_perform_action(action_string, connection_string, **kwargs)
            return result

    def to_dict(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "model": self.model,
            "model_provider": self.model_provider,
            "bio": self.bio,
            "traits": self.traits,
            "examples": self.examples,
            "timeline_read_count": self.timeline_read_count,
            "replies_per_tweet": self.replies_per_tweet,
            "loop_delay": self.loop_delay
        }

    def prompt_llm(self, prompt, **kwargs):
        # TODO: Create system prompt from agent bio, traits, examples
        system_prompt = "You are a helpful assistant."
        return self.connection_manager.find_and_perform_action(
            action_string="generate-text",
            connection_string=self.model_provider,
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.model,
            **kwargs)

    def set_preferred_model(self, model):
        # Check if model is valid
        result = self.connection_manager.find_and_perform_action(
            action_string="check-model",
            connection_string=self.model_provider,
            model=model)
        if result:
            self.model = model
            print("Model successfully changed.")

            # Update agent file
            agent_dict = self.to_dict()
            create_agent_file_from_dict(agent_dict)
        else:
            print("Model not valid for current provider. No changes made.")

    def set_preferred_model_provider(self, model_provider):
        self.model_provider = model_provider

        # Update agent file
        agent_dict = self.to_dict()
        create_agent_file_from_dict(agent_dict)

    def list_available_models(self):
        self.connection_manager.find_and_perform_action(
            action_string="list-models",
            connection_string=self.model_provider)


def load_agent_from_file(agent_path: str, connection_manager: ConnectionManager) -> ZerePyAgent:
    try:
        # Get agent fields from json file
        agent_dict = json.load(open(agent_path, "r"))

        # Create agent object
        agent = ZerePyAgent(
            name=agent_dict["name"],
            display_name=agent_dict["display_name"],
            model=agent_dict["model"],
            model_provider=agent_dict["model_provider"],
            connection_manager=connection_manager,
            bio=agent_dict["bio"],
            traits=agent_dict["traits"],
            examples=agent_dict["examples"],
            timeline_read_count=agent_dict["timeline_read_count"],
            replies_per_tweet=agent_dict["replies_per_tweet"],
            loop_delay=agent_dict["loop_delay"]
        )
    except FileNotFoundError:
        raise FileNotFoundError(f"Agent file not found at path: {agent_path}")
    except KeyError:
        raise KeyError(f"Agent file is missing a required field.")
    except Exception as e:
        raise Exception(f"An error occurred while loading the agent: {e}")
    
    logger.info(f"\n✅ Successfully loaded agent: {agent.display_name}")
    return agent


def create_agent_file_from_dict(agent_dict: dict):
    try:
        # Create agent file
        with open(f"agents/{agent_dict['name']}.json", "w") as file:
            # Save agent dict to json file
            json.dump(agent_dict, file, indent=4)
    except Exception as e:
        raise Exception(f"An error occurred while creating the agent file: {e}")
