import os
import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional
from dotenv import set_key, load_dotenv
import discord
from discord.ext import commands
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.discord_connection")
logger.setLevel(logging.DEBUG)

class DiscordConnectionError(Exception):
    """Base exception for Discord connection errors"""
    pass

class DiscordConfigurationError(DiscordConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class DiscordAPIError(DiscordConnectionError):
    """Raised when Discord API requests fail"""
    pass

class CustomDiscordBot(commands.Bot):
    """Custom bot class to handle events and message handling"""
    def __init__(self, llm_callback=None):
        logger.info("Initializing CustomDiscordBot...")
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(command_prefix='!', intents=intents)
        self.connection_ready = asyncio.Event()
        self.llm_callback = llm_callback
        self._connected = False
        
    async def on_ready(self):
        """Called when the bot successfully connects to Discord"""
        self._connected = True
        self.connection_ready.set()
        logger.info(f"✅ Bot connected successfully as {self.user}")

    async def on_message(self, message):
        """Called when a message is received"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            logger.debug(f"Ignoring message from self: {message.content[:50]}...")
            return

        logger.info(f"📥 Received message from {message.author}: {message.content[:50]}...")
        
        if not self.llm_callback:
            logger.error("❌ No LLM callback set for Discord bot")
            return
            
        logger.info("Generating response via LLM...")

        try:
            # Generate response using LLM
            prompt = f"Respond to this Discord message: {message.content}\nKeep responses natural and conversational."
            response = self.llm_callback(prompt)
            
            # Send the response
            if response:
                logger.info(f"🚀 Sending response: {response[:50]}...")
                await message.channel.send(
                    content=response,
                    reference=message,
                    mention_author=True
                )
                logger.info("✅ Response sent successfully")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")

    async def close(self):
        """Called when the bot is shutting down"""
        logger.info("🛑 Bot is shutting down...")
        self._connected = False
        self.connection_ready.clear()
        await super().close()
        logger.info("✅ Bot shutdown complete")

    @property
    def is_connected(self) -> bool:
        """Check if bot is currently connected"""
        return self._connected and self.is_ready()

class DiscordConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing DiscordConnection...")
        self._bot: Optional[CustomDiscordBot] = None
        self._bot_thread: Optional[threading.Thread] = None
        self._running = False
        self._llm_callback = None
        # Initialize with empty config since we don't need any
        super().__init__({})
        logger.info("✅ DiscordConnection initialized")

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Discord configuration - no config needed"""
        logger.debug("Validating Discord configuration...")
        return {}

    def register_actions(self) -> None:
        """Register available Discord actions"""
        logger.info("📝 Registering Discord actions...")
        # No actions needed as everything is event-driven
        self.actions = {}
        logger.info("✅ Discord actions registered")

    def set_llm_callback(self, callback):
        """Set the callback for LLM text generation"""
        logger.info("Setting up LLM callback for Discord bot")
        self._llm_callback = callback
        # If bot already exists, update its callback
        if self._bot:
            self._bot.llm_callback = callback
        logger.info("LLM callback configured")

    def _run_bot_forever(self):
        """Run the bot in a background thread"""
        logger.info("🚀 Starting bot in background thread...")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the bot
            loop.run_until_complete(self._initialize_bot())
            logger.info("✅ Bot initialization complete, running forever...")
            loop.run_forever()
        except Exception as e:
            logger.error(f"❌ Error in bot thread: {e}")
            self._running = False
        finally:
            logger.info("🛑 Bot thread shutting down...")
            loop.close()

    def _ensure_bot_running(self):
        """Ensure the bot is running in the background"""
        if not self._running:
            logger.info("Starting bot background thread...")
            self._running = True
            self._bot_thread = threading.Thread(target=self._run_bot_forever, daemon=True)
            self._bot_thread.start()
            logger.info("✅ Bot background thread started")
        else:
            logger.debug("Bot already running")

    async def _initialize_bot(self) -> None:
        """Initialize and connect the Discord bot"""
        if self._bot and self._bot.is_connected:
            logger.debug("Bot already initialized and connected")
            return

        logger.info("🚀 Initializing Discord bot...")
        
        token = os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            raise DiscordConfigurationError("Discord bot token not found")

        try:
            self._bot = CustomDiscordBot(self._llm_callback)
            await self._bot.start(token)
            logger.info("✅ Bot initialization complete")
        except Exception as e:
            self._bot = None
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise DiscordConfigurationError(f"Failed to initialize bot: {str(e)}")

    def configure(self) -> bool:
        """Sets up Discord bot authentication"""
        logger.info("\n🤖 DISCORD BOT SETUP")

        if self.is_configured():
            logger.info("Bot is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        print("\n📝 To get your Discord bot token:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Create a new application or select an existing one")
        print("3. Go to the Bot section and create a bot if you haven't already")
        print("4. Enable MESSAGE CONTENT INTENT in the Bot section")
        print("5. Copy your bot token")
        
        bot_token = input("\nEnter your Discord bot token: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            logger.info("Saving bot token to .env file...")
            set_key('.env', 'DISCORD_BOT_TOKEN', bot_token)
            
            # Simple validation of token format
            if not bot_token.strip() or len(bot_token.split('.')) != 3:
                logger.error("❌ Invalid token format")
                return False

            logger.info("✅ Discord bot configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"❌ Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if Discord bot token is configured and valid"""
        try:
            logger.debug("Checking Discord configuration...")
            load_dotenv()
            token = os.getenv('DISCORD_BOT_TOKEN')
            
            if not token:
                logger.debug("No token found")
                return False

            # If bot is already running and connected, we're good
            if self._bot and self._bot.is_connected:
                logger.debug("Bot is running and connected")
                return True

            # Basic validation
            token_parts = token.strip().split('.')
            if len(token_parts) != 3:
                logger.debug("Invalid token format")
                return False

            logger.debug("Configuration check passed")
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def start(self, connection_manager=None):
        """Start the Discord bot with automatic LLM setup"""
        if connection_manager:
            # Find the first available LLM provider
            llm_providers = [
                name for name, conn in connection_manager.connections.items()
                if conn.is_configured() and conn.is_llm_provider
            ]
            
            if llm_providers:
                llm_provider = llm_providers[0]
                logger.info(f"Using {llm_provider} as LLM provider for Discord")
                
                def llm_callback(prompt: str) -> str:
                    try:
                        # Use the LLM provider's generate-text action
                        return connection_manager.perform_action(
                            connection_name=llm_provider,
                            action_name="generate-text",
                            params=[prompt, "You are a helpful AI assistant."]
                        )
                    except Exception as e:
                        logger.error(f"Error generating LLM response: {e}")
                        return None
                
                # Set the callback
                self.set_llm_callback(llm_callback)
                logger.info(f"✅ LLM callback configured using {llm_provider}")
            else:
                logger.error("❌ No configured LLM provider found")
                return False
        
        # Start the bot
        self._ensure_bot_running()
        return True

    def stop(self):
        """Stop the Discord bot"""
        if self._bot:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._bot.close())
            finally:
                loop.close()
            self._bot = None
            self._running = False