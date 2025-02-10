import os
import logging
from typing import Dict, Any, Optional, cast, List
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
from src.types.connections import DiscordConfig
from src.types.config import BaseConnectionConfig
import requests
import json

logger = logging.getLogger("connections.discord_connection")


class DiscordConnectionError(Exception):
    """Base exception for Discord connection errors"""

    pass


class DiscordConfigurationError(DiscordConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class DiscordAPIError(DiscordConnectionError):
    """Raised when Discord API requests fail"""

    pass


class DiscordConnection(BaseConnection):
    base_url: str = "https://discord.com/api/v10"
    bot_username: Optional[str] = None
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Discord connection...")
        # Validate config before passing to super
        validated_config = DiscordConfig(**config)
        super().__init__(validated_config)
        self.base_url = "https://discord.com/api/v10"
        self.bot_username = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Discord configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = DiscordConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Discord configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Discord actions"""
        self.actions = {
            "read-messages": self.read_messages,
            "read-mentioned-messages": self.read_mentioned_messages,
            "post-message": self.post_message,
            "reply-to-message": self.reply_to_message,
            "react-to-message": self.react_to_message,
            "list-channels": self.list_channels
        }

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Discord API authentication"""
        print("\n🤖 DISCORD API SETUP")

        if self.is_configured():
            print("\nDiscord API is already configured.")
            response = kwargs.get("response") or input("Do you want to reconfigure? (y/n): ")
            if response.lower() != "y":
                return True

        setup_instructions = [
            "\n📝 Discord AUTHENTICATION SETUP",
            "\nℹ️ To get your Discord API credentials:",
            "1. Follow Discord's API documentation here: https://www.postman.com/discord-api/discord-api/collection/0d7xls9/discord-rest-api",
            "2. Copy the Discod token generated during the setup.",
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        api_key = kwargs.get("api_key") or input("\nEnter your Discord token: ")

        try:
            if not os.path.exists(".env"):
                with open(".env", "w") as f:
                    f.write("")

            set_key(".env", "DISCORD_TOKEN", api_key)

            self._test_connection(api_key)

            print("\n✅ Discord API configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Discord API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv("DISCORD_TOKEN")
            if not api_key:
                return False

            self._test_connection(api_key)
            return True
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute a Discord action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Add config parameters if not provided
        config = cast(DiscordConfig, self.config)
        if action_name == "read-messages":
            if "count" not in kwargs:
                kwargs["count"] = config.message_limit
        elif action_name == "read-mentioned-messages":
            if "count" not in kwargs:
                kwargs["count"] = config.message_limit
        elif action_name == "react-to-message":
            if "emoji_name" not in kwargs:
                kwargs["emoji_name"] = "👍"  # Default emoji if not specified
        elif action_name == "list-channels":
            if "server_id" not in kwargs:
                kwargs["server_id"] = config.guild_id

        # Call the appropriate method based on action name
        method_name = action_name.replace("-", "_")
        method = getattr(self, method_name)
        return method(**kwargs)

    def list_channels(self, server_id: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Lists all Discord channels under the server"""
        request_path = f"/guilds/{server_id}/channels"
        response = self._get_request(request_path)
        text_channels = self._filter_channels_for_type_text(cast(List[Dict[str, Any]], response))
        formatted_response = self._format_channels(text_channels)

        logger.info(f"Retrieved {len(formatted_response)} channels")
        return formatted_response

    def read_messages(self, channel_id: str, count: int, **kwargs: Any) -> List[Dict[str, Any]]:
        """Reading messages in a channel"""
        logger.debug("Sending a new message")
        request_path = f"/channels/{channel_id}/messages?limit={count}"
        response = self._get_request(request_path)
        formatted_response = self._format_messages(cast(List[Dict[str, Any]], response))

        logger.info(f"Retrieved {len(formatted_response)} messages")
        return formatted_response

    def read_mentioned_messages(self, channel_id: str, count: int, **kwargs: Any) -> List[Dict[str, Any]]:
        """Reads messages in a channel and filters for bot mentioned messages"""
        messages = self.read_messages(channel_id, count)
        mentioned_messages = self._filter_message_for_bot_mentions(messages)

        logger.info(f"Retrieved {len(mentioned_messages)} mentioned messages")
        return mentioned_messages

    def post_message(self, channel_id: str, message: str, **kwargs: Any) -> Dict[str, Any]:
        """Send a new message"""
        logger.debug("Sending a new message")

        request_path = f"/channels/{channel_id}/messages"
        payload = json.dumps({"content": f"{message}"})
        response = self._post_request(request_path, payload)
        formatted_response = self._format_posted_message(response)

        logger.info("Message posted successfully")
        return formatted_response

    def reply_to_message(
        self, channel_id: str, message_id: str, message: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Reply to a message"""
        logger.debug("Replying to a message")

        request_path = f"/channels/{channel_id}/messages"
        payload = json.dumps(
            {
                "content": f"{message}",
                "message_reference": {
                    "channel_id": f"{channel_id}",
                    "message_id": f"{message_id}",
                },
            }
        )
        response = self._post_request(request_path, payload)
        formatted_response = self._format_reply_message(response)

        logger.info("Reply message posted successfully")
        return formatted_response

    def react_to_message(
        self, channel_id: str, message_id: str, emoji_name: str, **kwargs: Any
    ) -> None:
        """React to a message"""
        logger.debug("Reacting to a message")

        request_path = (
            f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji_name}/@me"
        )
        self._put_request(request_path)

        logger.info("Reacted to message successfully")
        return

    def _format_reply_message(self, reply_message: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to format reply messages"""
        mentions = []
        for mention in reply_message["mentions"]:
            mentions.append({"id": mention["id"], "username": mention["username"]})
        return {
            "id": reply_message["id"],
            "channel_id": reply_message["channel_id"],
            "author": reply_message["author"]["username"],
            "content": reply_message["content"],
            "timestamp": reply_message["timestamp"],
            "mentions": mentions,
        }

    def _format_posted_message(self, posted_message: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to format posted messages"""
        mentions = []
        for mention in posted_message["mentions"]:
            mentions.append({"id": mention["id"], "username": mention["username"]})

        return {
            "id": posted_message["id"],
            "channel_id": posted_message["channel_id"],
            "content": posted_message["content"],
            "timestamp": posted_message["timestamp"],
            "mentions": mentions,
        }

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper method to format messages"""
        formatted_messages = []
        for message in messages:
            mentions = []
            for mention in message["mentions"]:
                mentions.append({"id": mention["id"], "username": mention["username"]})
            formatted_message = {
                "id": message["id"],
                "channel_id": message["channel_id"],
                "author": message["author"]["username"],
                "message": message["content"],
                "timestamp": message["timestamp"],
                "mentions": mentions,
            }
            formatted_messages.append(formatted_message)
        return formatted_messages

    def _format_channels(self, channels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper method to format channels"""
        formatted_channels = []
        for channel in channels:
            formatted_channel = {
                "id": channel["id"],
                "type": channel["type"],
                "name": channel["name"],
                "server_id": channel["guild_id"],
            }
            formatted_channels.append(formatted_channel)
        return formatted_channels

    def _put_request(self, url_path: str) -> None:
        """Helper method to make PUT request"""
        url = f"{self.base_url}{url_path}"
        headers = {
            "Accept": "application/json",
            "Authorization": self._get_request_auth_token(),
        }
        response = requests.request("PUT", url, headers=headers, data={})
        if response.status_code != 204:
            raise DiscordAPIError(
                f"Failed to called PUT to Discord: {response.status_code} - {response.text}"
            )
        return

    def _post_request(self, url_path: str, payload: str) -> Dict[str, Any]:
        """Helper method to make POST request"""
        url = f"{self.base_url}{url_path}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": self._get_request_auth_token(),
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code != 200:
            raise DiscordAPIError(
                f"Failed to call POST to Discord: {response.status_code} - {response.text}"
            )
        response_data: Dict[str, Any] = json.loads(response.text)
        return response_data

    def _get_request(self, url_path: str) -> Dict[str, Any]:
        """Helper method to make GET request"""
        url = f"{self.base_url}{url_path}"
        headers = {
            "Accept": "application/json",
            "Authorization": self._get_request_auth_token(),
        }
        response = requests.request("GET", url, headers=headers, data={})
        if response.status_code != 200:
            raise DiscordAPIError(
                f"Failed to call GET to Discord: {response.status_code} - {response.text}"
            )
        response_data: Dict[str, Any] = json.loads(response.text)
        return response_data

    def _get_request_auth_token(self) -> str:
        return f"Bot {os.getenv('DISCORD_TOKEN')}"

    def _test_connection(self, api_key: str) -> None:
        """Helper method to check if Discord is reachable"""
        try:
            url = f"{self.base_url}/users/@me"
            headers = {"Accept": "application/json", "Authorization": f"Bot {api_key}"}
            response = requests.request("GET", url, headers=headers, data={})
            if response.status_code != 200:
                raise DiscordAPIError(
                    f"Failed to call GET to Discord: {response.status_code} - {response.text}"
                )

            response_data = json.loads(response.text)
            self.bot_username = response_data["username"]

        except Exception as e:
            raise DiscordConnectionError(f"Connection test failed: {e}")

    def _filter_channels_for_type_text(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Helper method to filter for only channels that are text channels"""
        filtered_data = []
        for item in data:
            if item["type"] == 0:
                filtered_data.append(item)
        return filtered_data

    def _filter_message_for_bot_mentions(
        self,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Helper method to filter for messages that mention the bot"""
        filtered_data = []
        for item in data:
            for mention in item["mentions"]:
                if mention["username"] == self.bot_username:
                    filtered_data.append(item)
        return filtered_data
