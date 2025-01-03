import json
import random
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar

REQUIRED_FIELDS = ["name", "bio", "traits", "examples", "loop_delay", "config", "tasks"]

logger = logging.getLogger("agent")

class ZerePyAgent:
    def __init__(
            self,
            agent_name: str
    ):
        try:
            agent_path = Path("agents") / f"{agent_name}.json"
            agent_dict = json.load(open(agent_path, "r"))

            missing_fields = [field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            self.name = agent_dict["name"]
            self.bio = agent_dict["bio"]
            self.traits = agent_dict["traits"]
            self.examples = agent_dict["examples"]
            self.loop_delay = agent_dict["loop_delay"]
            self.connection_manager = ConnectionManager(agent_dict["config"])

            # Extract Twitter config if Twitter tasks exist
            has_twitter_tasks = any(task["name"].startswith("tweet") or task["name"].startswith("like-tweet") 
                                  for task in agent_dict.get("tasks", []))
            
            twitter_config = next((config for config in agent_dict["config"] if config["name"] == "twitter"), None)
            if has_twitter_tasks and twitter_config:
                self.tweet_interval = twitter_config.get("tweet_interval", 900)
                self.own_tweet_replies_count = twitter_config.get("own_tweet_replies_count", 2)

            # Extract Echochambers config
            echochambers_config = next((config for config in agent_dict["config"] if config["name"] == "echochambers"), None)
            if echochambers_config:
                self.echochambers_message_interval = echochambers_config.get("message_interval", 60)
                self.echochambers_history_count = echochambers_config.get("history_read_count", 50)

            self.is_llm_set = False

            # Cache for system prompt
            self._system_prompt = None

            # Extract loop tasks
            self.tasks = agent_dict.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]

            # Set up empty agent state
            self.state = {}

        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise e

    def _setup_llm_provider(self):
        # Get first available LLM provider and its model
        llm_providers = self.connection_manager.get_model_providers()
        if not llm_providers:
            raise ValueError("No configured LLM provider found")
        self.model_provider = llm_providers[0]

        # Load Twitter username for self-reply detection if Twitter tasks exist
        if any(task["name"].startswith("tweet") for task in self.tasks):
            load_dotenv()
            self.username = os.getenv('TWITTER_USERNAME', '').lower()
            if not self.username:
                logger.warning("Twitter username not found, some Twitter functionalities may be limited")

    def _construct_system_prompt(self) -> str:
        """Construct the system prompt from agent configuration"""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)

            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples:
                prompt_parts.append("\nHere are some examples of your style (Please avoid repeating any of these):")
                prompt_parts.extend(f"- {example}" for example in self.examples)

            self._system_prompt = "\n".join(prompt_parts)

        return self._system_prompt

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

        last_tweet_time = 0

        try:
            while True:
                success = False
                try:
                    # REPLENISH INPUTS
                    # TODO: Add more inputs to complexify agent behavior
                    if "timeline_tweets" not in self.state or self.state["timeline_tweets"] is None or len(self.state["timeline_tweets"]) == 0:
                        if any(task["name"].startswith("tweet") for task in self.tasks):
                            logger.info("\n👀 READING TIMELINE")
                            self.state["timeline_tweets"] = self.connection_manager.perform_action(
                                connection_name="twitter",
                                action_name="read-timeline",
                                params=[]
                            )

                    # CHOOSE AN ACTION
                    # TODO: Add agentic action selection
                    action = random.choices(self.tasks, weights=self.task_weights, k=1)[0]
                    action_name = action["name"]

                    # PERFORM ACTION
                    if action_name == "post-tweet":
                        # Check if it's time to post a new tweet
                        current_time = time.time()
                        if current_time - last_tweet_time >= self.tweet_interval:
                            logger.info("\n📝 GENERATING NEW TWEET")
                            print_h_bar()

                            prompt = ("Generate an engaging tweet. Don't include any hashtags, links or emojis. Keep it under 280 characters."
                                    f"The tweets should be pure commentary, do not shill any coins or projects apart from {self.name}. Do not repeat any of the"
                                    "tweets that were given as example. Avoid the words AI and crypto.")
                            tweet_text = self.prompt_llm(prompt)

                            if tweet_text:
                                logger.info("\n🚀 Posting tweet:")
                                logger.info(f"'{tweet_text}'")
                                self.connection_manager.perform_action(
                                    connection_name="twitter",
                                    action_name="post-tweet",
                                    params=[tweet_text]
                                )
                                last_tweet_time = current_time
                                success = True
                                logger.info("\n✅ Tweet posted successfully!")
                        else:
                            logger.info("\n👀 Delaying post until tweet interval elapses...")
                            print_h_bar()
                            continue

                    elif action_name == "reply-to-tweet":
                        if "timeline_tweets" in self.state and self.state["timeline_tweets"] is not None and len(self.state["timeline_tweets"]) > 0:
                            # Get next tweet from inputs
                            tweet = self.state["timeline_tweets"].pop(0)
                            tweet_id = tweet.get('id')
                            if not tweet_id:
                                continue

                            # Check if it's our own tweet using username
                            is_own_tweet = tweet.get('author_username', '').lower() == self.username
                            if is_own_tweet:
                                # pick one of the replies to reply to
                                replies = self.connection_manager.perform_action(
                                    connection_name="twitter",
                                    action_name="get-tweet-replies",
                                    params=[tweet.get('author_id')]
                                )
                                if replies:
                                    self.state["timeline_tweets"].extend(replies[:self.own_tweet_replies_count])
                                continue

                            logger.info(f"\n💬 GENERATING REPLY to: {tweet.get('text', '')[:50]}...")

                            # Customize prompt based on whether it's a self-reply
                            base_prompt = (f"Generate a friendly, engaging reply to this tweet: {tweet.get('text')}. Keep it under 280 characters. Don't include any usernames, hashtags, links or emojis. "
                                f"The tweets should be pure commentary, do not shill any coins or projects apart from {self.name}. Do not repeat any of the"
                                "tweets that were given as example. Avoid the words AI and crypto.")

                            system_prompt = self._construct_system_prompt()
                            reply_text = self.prompt_llm(prompt=base_prompt, system_prompt=system_prompt)

                            if reply_text:
                                logger.info(f"\n🚀 Posting reply: '{reply_text}'")
                                self.connection_manager.perform_action(
                                    connection_name="twitter",
                                    action_name="reply-to-tweet",
                                    params=[tweet_id, reply_text]
                                )
                                success = True
                                logger.info("✅ Reply posted successfully!")

                    elif action_name == "like-tweet":
                        if "timeline_tweets" in self.state and self.state["timeline_tweets"] is not None and len(self.state["timeline_tweets"]) > 0:
                            # Get next tweet from inputs
                            tweet = self.state["timeline_tweets"].pop(0)
                            tweet_id = tweet.get('id')
                            if not tweet_id:
                                continue

                            logger.info(f"\n👍 LIKING TWEET: {tweet.get('text', '')[:50]}...")

                            self.connection_manager.perform_action(
                                connection_name="twitter",
                                action_name="like-tweet",
                                params=[tweet_id]
                            )
                            success = True
                            logger.info("✅ Tweet liked successfully!")

                    # Handle Echochambers tasks
                    elif action_name.startswith("post-echochambers") or action_name.startswith("reply-echochambers"):
                        current_time = time.time()
                        
                        # Get room info
                        room_info = self.connection_manager.perform_action(
                            connection_name="echochambers",
                            action_name="get-room-info",
                            params={}
                        )

                        # Initialize state
                        if "echochambers_last_message" not in self.state:
                            self.state["echochambers_last_message"] = 0
                        if "echochambers_replied_messages" not in self.state:
                            self.state["echochambers_replied_messages"] = set()
                        
                        if action_name == "post-echochambers" and current_time - self.state["echochambers_last_message"] > self.echochambers_message_interval:
                            logger.info("\n📝 GENERATING NEW ECHOCHAMBERS MESSAGE")
                            
                            # Generate message based on room topic and tags
                            previous_messages = self.connection_manager.connections["echochambers"].sent_messages
                            previous_content = "\n".join([f"- {msg['content']}" for msg in previous_messages])
                            logger.info(f"Found {len(previous_messages)} messages in post history")
                            
                            prompt=f"Context:\n- Room Topic: {room_info['topic']}\n- Tags: {', '.join(room_info['tags'])}\n- Previous Messages:\n{previous_content}\n\nTask:\nCreate a concise, engaging message that:\n1. Aligns with the room's topic and tags\n2. Builds upon Previous Messages without repeating them, or repeating greetings, introductions, or sentences.\n3. Offers fresh insights or perspectives\n4. Maintains a natural, conversational tone\n5. Keeps length between 2-4 sentences\n\nGuidelines:\n- Be specific and relevant\n- Add value to the ongoing discussion\n- Avoid generic statements\n- Use a friendly but professional tone\n- Include a question or discussion point when appropriate\n\nThe message should feel organic and contribute meaningfully to the conversation."
                            message=self.prompt_llm(prompt)
                            
                            if message:
                                logger.info(f"\n🚀 Posting message: '{message[:69]}...'")
                                self.connection_manager.perform_action(
                                    connection_name="echochambers",
                                    action_name="send-message",
                                    params=[message]  # Pass as list of values
                                )
                                self.state["echochambers_last_message"] = current_time
                                success = True
                                logger.info("✅ Message posted successfully!")
                        
                        elif action_name == "reply-echochambers":
                            logger.info("\n🔍 CHECKING FOR MESSAGES TO REPLY TO")
                            
                            # Initialize replied messages set if not exists
                            if "echochambers_replied_messages" not in self.state:
                                self.state["echochambers_replied_messages"] = set()
                                
                            # Get recent messages
                            history = self.connection_manager.perform_action(
                                connection_name="echochambers",
                                action_name="get-room-history",
                                params={}
                            )
                            
                            # Find most recent message we haven't replied to
                            if history:
                                logger.info(f"Found {len(history)} messages in history")
                                for message in history:
                                    message_id = message.get('id')
                                    sender = message.get('sender', {})
                                    sender_username = sender.get('username')
                                    content = message.get('content', '')
                                    
                                    if not message_id or not sender_username or not content:
                                        logger.warning(f"Skipping message with missing fields: {message}")
                                        continue
                                    
                                    # Skip if:
                                    # 1. It's our message
                                    # 2. We've already replied to it
                                    if (sender_username == self.connection_manager.connections["echochambers"].config["sender_username"] or 
                                        message_id in self.state.get("echochambers_replied_messages", set())):
                                        logger.info(f"Skipping message from {sender_username} (already replied or own message)")
                                        continue
                                        
                                    logger.info(f"\n💬 GENERATING REPLY to: @{sender_username} - {content[:69]}...")
                                    
                                    # Generate contextual reply
                                    refer_username = random.random() < 0.7
                                    username_prompt = f"Refer the sender by their @{sender_username}" if refer_username else "Respond without directly referring to the sender"
                                    prompt = f"Context:\n- Current Message: \"{content}\"\n- Sender Username: @{sender_username}\n- Room Topic: {room_info['topic']}\n- Tags: {', '.join(room_info['tags'])}\n\nTask:\nCraft a reply that:\n1. Addresses the message\n2. Aligns with topic/tags\n3. Engages participants\n4. Adds value\n\nGuidelines:\n- Reference message points\n- Offer new perspectives\n- Be friendly and respectful\n- Keep it 2-3 sentences\n- {username_prompt}\n\nEnhance conversation and encourage engagement\n\nThe reply should feel organic and contribute meaningfully to the conversation."
                                    reply = self.prompt_llm(prompt)
                                    
                                    if reply:
                                        logger.info(f"\n🚀 Posting reply: '{reply[:69]}...'")
                                        self.connection_manager.perform_action(
                                            connection_name="echochambers",
                                            action_name="send-message",
                                            params=[reply]  # Pass as list of values
                                        )
                                        # Track that we replied to this message
                                        self.state["echochambers_replied_messages"].add(message_id)
                                        success = True
                                        logger.info("✅ Reply posted successfully!")
                                        break
                            else:
                                logger.info("No messages in history")

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