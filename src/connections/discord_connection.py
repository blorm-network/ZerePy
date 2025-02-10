import os
import logging
from typing import Dict, Any
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
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
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = "https://discord.com/api/v10"
        self.bot_username = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Discord configuration from JSON"""
        required_fields = ["server_id", "message_read_count", "message_emoji_name"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )

        if (
            not isinstance(config["message_read_count"], int)
            or config["message_read_count"] <= 0
        ):
            raise ValueError("message_read_count must be a positive integer")
        if (
            not isinstance(config["message_emoji_name"], str)
            or len(config["message_emoji_name"]) <= 0
        ):
            raise ValueError("message_emoji_name must be a valid string")
        if not isinstance(config["server_id"], str) or len(config["server_id"]) <= 0:
            raise ValueError("server_id must be a valid string")

        return config

    def register_actions(self) -> None:
        """Register available Discord actions"""
        self.actions = {
            "read-messages": Action(
                name="read-messages",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        True,
                        str,
                        "The channel id to get messages from",
                    ),
                    ActionParameter(
                        "count",
                        False,
                        int,
                        "Number of messages to retrieve",
                    ),
                ],
                description="Get the latest messages from a channel",
            ),
            "read-mentioned-messages": Action(
                name="read-mentioned-messages",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        True,
                        str,
                        "The channel id to get messages from",
                    ),
                    ActionParameter(
                        "count",
                        False,
                        int,
                        "Number of messages to retrieve",
                    ),
                ],
                description="Get the latest messages that mention the bot",
            ),
            "post-message": Action(
                name="post-message",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        True,
                        str,
                        "The channel id for the message to be posted in",
                    ),
                    ActionParameter(
                        "message", True, str, "Text content of the message"
                    ),
                ],
                description="Post a new message",
            ),
            "reply-to-message": Action(
                name="reply-to-message",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        True,
                        str,
                        "The channel id to get messages from",
                    ),
                    ActionParameter(
                        "message_id", True, str, "ID of the message to reply to"
                    ),
                    ActionParameter("message", True, str, "Reply message content"),
                ],
                description="Reply to an existing message",
            ),
            "react-to-message": Action(
                name="react-to-message",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        True,
                        str,
                        "The channel id for the message to be posted in",
                    ),
                    ActionParameter(
                        "message_id", True, str, "ID of the message to reply to"
                    ),
                    ActionParameter(
                        "emoji_name",
                        False,
                        str,
                        "Name of the emoji to put on the message",
                    ),
                ],
                description="Post a new message",
            ),
            "list-channels": Action(
                name="list-channels",
                parameters=[
                    ActionParameter(
                        "server_id",
                        False,
                        str,
                        "The server id to list channels from",
                    ),
                ],
                description="List all the channels for a specified discord server",
            ),
        }

    def configure(self) -> bool:
        """Sets up Discord API authentication"""
        print("\n🤖 DISCORD API SETUP")

        if self.is_configured():
            print("\nDiscord API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
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

        api_key = input("\nEnter your Discord token: ")

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

    def is_configured(self, verbose=False) -> bool:
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

    def perform_action(self, action_name: str, kwargs) -> Any:
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Add config parameters if not provided
        if action_name == "read-messages":
            if "count" not in kwargs:
                kwargs["count"] = self.config["message_read_count"]
        elif action_name == "read-mentioned-messages":
            if "count" not in kwargs:
                kwargs["count"] = self.config["message_read_count"]
        elif action_name == "react-to-message":
            if "emoji_name" not in kwargs:
                kwargs["emoji_name"] = self.config["message_emoji_name"]
        elif action_name == "list-channels":
            if "server_id" not in kwargs:
                kwargs["server_id"] = self.config["server_id"]

        # Call the appropriate method based on action name
        method_name = action_name.replace("-", "_")
        method = getattr(self, method_name)
        return method(**kwargs)

    def list_channels(self, server_id: str, **kwargs) -> dict:
        """Lists all Discord channels under the server"""
        request_path = f"/guilds/{server_id}/channels"
        response = self._get_request(request_path)
        text_channels = self._filter_channels_for_type_text(response)
        formatted_response = self._format_channels(text_channels)

        logger.info(f"Retrieved {len(formatted_response)} channels")
        return formatted_response

    def read_messages(self, channel_id: str, count: int, **kwargs) -> dict:
        """Reading messages in a channel"""
        logger.debug("Sending a new message")
        request_path = f"/channels/{channel_id}/messages?limit={count}"
        response = self._get_request(request_path)
        formatted_response = self._format_messages(response)

        logger.info(f"Retrieved {len(formatted_response)} messages")
        return formatted_response

    def read_mentioned_messages(self, channel_id: str, count: int, **kwargs) -> dict:
        """Reads messages in a channel and filters for bot mentioned messages"""
        messages = self.read_messages(channel_id, count)
        mentioned_messages = self._filter_message_for_bot_mentions(messages)

        logger.info(f"Retrieved {len(mentioned_messages)} mentioned messages")
        return mentioned_messages

    def post_message(self, channel_id: str, message: str, **kwargs) -> dict:
        """Send a new message"""
        logger.debug("Sending a new message")

        request_path = f"/channels/{channel_id}/messages"
        payload = json.dumps({"content": f"{message}"})
        response = self._post_request(request_path, payload)
        formatted_response = self._format_posted_message(response)

        logger.info("Message posted successfully")
        return formatted_response

    def reply_to_message(
        self, channel_id: str, message_id: str, message: str, **kwargs
    ) -> dict:
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
        self, channel_id: str, message_id: str, emoji_name: str, **kwargs
    ) -> None:
        """React to a message"""
        logger.debug("Reacting to a message")

        request_path = (
            f"/channels/{channel_id}/messages/{message_id}/reactions/{emoji_name}/@me"
        )
        self._put_request(request_path)

        logger.info("Reacted to message successfully")
        return

    def _format_reply_message(self, reply_message: dict) -> dict:
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

    def _format_posted_message(self, posted_message: dict) -> dict:
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

    def _format_messages(self, messages: dict) -> dict:
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

    def _format_channels(self, channels: dict) -> dict:
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

    def _post_request(self, url_path: str, payload: str) -> dict:
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
        return json.loads(response.text)

    def _get_request(self, url_path: str) -> str:
        """Helper method to make GET request"""
        url = f"{self.base_url}{url_path}"
        headers = {
            "Accept": "application/json",
            "Authorization": self._get_request_auth_token(),
        }
        print(headers)
        response = requests.request("GET", url, headers=headers, data={})
        if response.status_code != 200:
            raise DiscordAPIError(
                f"Failed to call GET to Discord: {response.status_code} - {response.text}"
            )
        return json.loads(response.text)

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

            self.bot_username = json.loads(response.text)["username"]

        except Exception as e:
            raise DiscordConnectionError(f"Connection test failed: {e}")

    def _filter_channels_for_type_text(self, data):
        """Helper method to filter for only channels that are text channels"""
        filtered_data = []
        for item in data:
            if item["type"] == 0:
                filtered_data.append(item)
        return filtered_data

    def _filter_message_for_bot_mentions(
        self,
        data,
    ):
        """Helper method to filter for messages that mention the bot"""
        filtered_data = []
        for item in data:
            for mention in item["mentions"]:
                if mention["username"] == self.bot_username:
                    filtered_data.append(item)
        return filtered_data
