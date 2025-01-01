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

            # Extract Twitter config
            twitter_config = next((config for config in agent_dict["config"] if config["name"] == "twitter"), None)
            if not twitter_config:
                raise KeyError("Twitter configuration is required")

            # TODO: These should probably live in the related task parameters
            self.tweet_interval = twitter_config.get("tweet_interval", 900)
            self.own_tweet_replies_count = twitter_config.get("own_tweet_replies_count", 2)

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

        # Load Twitter username for self-reply detection
        load_dotenv()
        self.username = os.getenv('TWITTER_USERNAME', '').lower()
        if not self.username:
                raise ValueError("Twitter username is required")

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
        rate_limit_wait = 900  # 15 minutes default wait for rate limits
        self.tweet_limit_reset = None  # Track when we can tweet again
        self.timeline_limit_reset = None  # Track timeline read limits

        try:
            while True:
                success = False
                try:
                    current_time = time.time()
                    
                    # Show current status
                    logger.info(f"\n{self._get_agent_status()}")
                    print_h_bar()
                    
                    # Check tweet limit cooldown
                    if self.tweet_limit_reset and current_time < self.tweet_limit_reset:
                        wait_seconds = self.tweet_limit_reset - current_time
                        hours = int(wait_seconds / 3600)
                        minutes = int((wait_seconds % 3600) / 60)
                        reset_time = self._format_time(self.tweet_limit_reset)
                        logger.info(f"\n⏳ In likes-only mode until {reset_time} ({hours}h {minutes}m)")

                    # Check timeline read limit
                    if self.timeline_limit_reset and current_time < self.timeline_limit_reset:
                        wait_seconds = self.timeline_limit_reset - current_time
                        minutes = int(wait_seconds / 60)
                        reset_time = self._format_time(self.timeline_limit_reset)
                        logger.info(f"\n⏳ Timeline rate limited until {reset_time} ({minutes}m)")
                        time.sleep(min(wait_seconds, self.loop_delay))
                        continue

                    # REPLENISH INPUTS
                    # TODO: Add more inputs to complexify agent behavior
                    if "timeline_tweets" not in self.state or self.state["timeline_tweets"] is None or len(self.state["timeline_tweets"]) == 0:
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

    def _get_context_from_timeline(self) -> str:
        """Extract relevant context and trends from timeline tweets"""
        if not self.state.get("timeline_tweets"):
            return ""
        
        # Get more context from recent tweets
        recent_tweets = self.state["timeline_tweets"][:10]  # Analyze last 10 tweets
        
        context = "Current conversation context:\n"
        
        # Define relevant topic categories
        topic_categories = {
            'defi': ['defi', 'web3', 'blockchain', 'crypto', 'ethereum', 'trading', 'finance'],
            'ai_agents': ['ai', 'agent', 'llm', 'gpt', 'autonomous', 'bot', 'automation'],
            'zerepy': ['zerepy', 'agent', 'developer', 'ecosystem', 'platform']
        }
        
        # Track topics by category
        category_mentions = {
            'defi': {},
            'ai_agents': {},
            'zerepy': {}
        }
        
        # Extract topics and analyze context
        active_discussions = []
        for tweet in recent_tweets:
            text = tweet.get('text', '').lower()
            if not text:
                continue
            
            # Track topics by category
            for category, keywords in topic_categories.items():
                for keyword in keywords:
                    if keyword in text:
                        words = text.split()
                        # Find contextual phrases around keyword
                        for i, word in enumerate(words):
                            if keyword in word:
                                start = max(0, i-2)
                                end = min(len(words), i+3)
                                phrase = ' '.join(words[start:end])
                                if phrase not in category_mentions[category]:
                                    category_mentions[category][phrase] = 0
                                category_mentions[category][phrase] += 1
            
            # Add full tweet for immediate context
            active_discussions.append(text)
        
        # Build context summary
        context += "\nActive Discussions:\n"
        for discussion in active_discussions[:3]:
            context += f"- {discussion}\n"
        
        # Add trending topics by category
        context += "\nTrending Topics:\n"
        for category, mentions in category_mentions.items():
            if mentions:
                trending = sorted(mentions.items(), key=lambda x: x[1], reverse=True)[:2]
                context += f"\n{category.upper()} Trends:\n"
                for topic, count in trending:
                    context += f"- {topic} (mentioned {count} times)\n"
        
        return context

    def _format_time(self, timestamp: float = None) -> str:
        """Format timestamp into human readable format"""
        if timestamp is None:
            timestamp = time.time()
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

    def _get_agent_status(self) -> str:
        """Get current agent status for display"""
        current_time = time.time()
        status_parts = []
        
        # Add timestamp
        status_parts.append(f"🕒 Current time: {self._format_time()}")
        
        # Add tweet limit status
        if hasattr(self, 'tweet_limit_reset') and self.tweet_limit_reset and current_time < self.tweet_limit_reset:
            wait_seconds = self.tweet_limit_reset - current_time
            hours = int(wait_seconds / 3600)
            minutes = int((wait_seconds % 3600) / 60)
            status_parts.append(f"🔄 Tweet Mode: LIKES ONLY (resumes in {hours}h {minutes}m)")
        else:
            status_parts.append("🔄 Tweet Mode: ACTIVE")
        
        # Add timeline status
        if hasattr(self, 'timeline_limit_reset') and self.timeline_limit_reset and current_time < self.timeline_limit_reset:
            wait_seconds = self.timeline_limit_reset - current_time
            minutes = int(wait_seconds / 60)
            status_parts.append(f"📚 Timeline: PAUSED (resumes in {minutes}m)")
        else:
            status_parts.append("📚 Timeline: ACTIVE")
        
        # Add queue status
        tweet_count = len(self.state.get("timeline_tweets", []))
        status_parts.append(f"📋 Queue: {tweet_count} tweets")
        
        return " | ".join(status_parts)
