import logging
import time
from typing import Dict, Any, List
from collections import deque

import requests
from dotenv import load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.echochambers_connection")

class EchochambersConnectionError(Exception):
    """Base exception for Echochambers connection errors"""
    pass

class EchochambersConfigurationError(EchochambersConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class EchochambersAPIError(EchochambersConnectionError):
    """Raised when Echochambers API requests fail"""
    pass

class EchochambersConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("✨ Initializing Echochambers adapter")
        super().__init__(config)

        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.room = config.get("room")
        self.sender_username = config.get("sender_username")
        self.sender_model = config.get("sender_model")
        self.history_read_count = config.get("history_read_count")
        self.post_history_track = config.get("post_history_track")

        # Validate essential configurations
        if not all([self.api_url, self.api_key, self.room, self.sender_username, self.sender_model, self.history_read_count, self.post_history_track]):
            missing = [k for k in ["api_url", "api_key", "room", "sender_username", "sender_model", "history_read_count", "post_history_track"]
                       if not getattr(self, k)]
            raise EchochambersConfigurationError(f"Missing configuration fields: {', '.join(missing)}")

        logger.info(f"✨ Connected to: {self.api_url}")
        logger.info(f"✨ Entered room: {self.room}")

        # Initialize message queue and tracking
        self.message_queue: List[Dict[str, Any]] = []
        self.processed_messages = set()
        self.max_queue_size = 100
        
        # Keep track of our last messages to ensure uniqueness
        self.sent_messages = deque(maxlen=self.post_history_track)

        # Initialize metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_failed': 0,
            'api_latency': [],
            'last_error': None,
            'last_metrics_log': time.time()
        }

        # Register actions
        self.register_actions()

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Echochambers configuration from JSON"""
        required_fields = ["api_url", "api_key", "room", "history_read_count", "sender_username", "sender_model"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        if not isinstance(config["history_read_count"], int) or config["history_read_count"] <= 0:
            raise ValueError("history_read_count must be a positive integer")

        return config

    def register_actions(self) -> None:
        """Register available Echochambers actions"""
        actions = [
            Action(
                name="get-room-info",
                description="Get information about the current room including topic and tags",
                parameters=[]
            ),
            Action(
                name="get-room-history",
                description="Get message history from the Echochambers room",
                parameters=[]
            ),
            Action(
                name="send-message",
                description="Send a message to the Echochambers room",
                parameters=[
                    ActionParameter(
                        name="content",
                        description="The message content to send",
                        required=True,
                        type=str
                    )
                ]
            ),
            Action(
                name="process-room-history",
                description="Process and queue messages for replies",
                parameters=[]
            )
        ]
        self.actions = {action.name: action for action in actions}

    def get_room_info(self) -> Dict[str, Any]:
        """Get information about the current room by listing all rooms and finding ours"""
        try:
            url = f"{self.api_url}/api/rooms"
            response = self._make_request("GET", url)
            room_info = next((room for room in response.get("rooms", []) if room["id"] == self.room), None)
            if not room_info:
                raise EchochambersAPIError(f"Room '{self.room}' not found")

            return {
                "id": room_info["id"],
                "name": room_info["name"],
                "topic": room_info.get("topic", "General Discussion"),
                "tags": room_info["tags"],
                "messageCount": room_info["messageCount"]
            }
        except Exception as e:
            self._handle_error("Failed to get room info", e)
            raise

    def get_room_history(self) -> List[Dict[str, Any]]:
        """Get message history from the room"""
        try:
            url = f"{self.api_url}/api/rooms/{self.room}/history"
            response = self._make_request("GET", url)
            messages = response.get('messages', [])
            return [
                {
                    "id": msg.get("id", ""),
                    "content": msg.get("content", ""),
                    "sender": {
                        "username": msg.get("sender", {}).get("username", ""),
                        "model": msg.get("sender", {}).get("model", "")
                    },
                    "timestamp": msg.get("timestamp", ""),
                    "roomId": msg.get("roomId", "")
                }
                for msg in messages[:self.history_read_count] if isinstance(msg, dict)
            ]
        except Exception as e:
            self._handle_error("Failed to get room history", e)
            raise

    def send_message(self, content: str) -> Dict[str, Any]:
        """Send a message to the room"""
        try:
            url = f"{self.api_url}/api/rooms/{self.room}/message"
            data = {
                "content": content,
                "sender": {
                    "username": self.sender_username,
                    "model": self.sender_model
                }
            }
            response = self._make_request("POST", url, json=data)
            self.metrics['messages_sent'] += 1
            
            # Add to sent messages history
            self.sent_messages.append({
                "content": content,
                "timestamp": time.time()
            })
            
            return response
        except Exception as e:
            self.metrics['messages_failed'] += 1
            self._handle_error("Failed to send message", e)
            raise

    def process_room_history(self) -> None:
        """Process and queue messages for replies"""
        try:
            history = self.get_room_history()

            # Process messages in reverse (oldest first)
            for message in reversed(history):
                if len(self.message_queue) >= self.max_queue_size:
                    break
                if (message['id'] not in self.processed_messages and
                        message['sender']['username'] != self.sender_username):
                    self.message_queue.append(message)
                    self.processed_messages.add(message['id'])

            logger.info(f"Queued {len(self.message_queue)} messages for processing")
            self._log_metrics()
        except Exception as e:
            self._handle_error("Failed to process room history", e)
            raise

    def _make_request(self, method: str, url: str, **kwargs) -> Any:
        """Make HTTP request with retries and error handling"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        kwargs['headers'] = headers

        for attempt in range(3):
            try:
                response = requests.request(method, url, timeout=10, **kwargs)
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit hit, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.Timeout:
                logger.error(f"Timeout on attempt {attempt + 1}")
                time.sleep(2 ** attempt)  # Exponential backoff
            except requests.RequestException as e:
                if attempt == 2:
                    raise EchochambersAPIError(f"Failed after 3 attempts: {str(e)}")
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2 ** attempt)

    def _handle_error(self, message: str, error: Exception) -> None:
        """Handle and log errors"""
        error_msg = f"{message}: {str(error)}"
        logger.error(error_msg)
        self.metrics['last_error'] = error_msg
        self._log_metrics()

    def _log_metrics(self) -> None:
        """Log performance metrics every 5 minutes"""
        current_time = time.time()
        if current_time - self.metrics['last_metrics_log'] >= 300:
            total_attempts = self.metrics['messages_sent'] + self.metrics['messages_failed']
            success_rate = (self.metrics['messages_sent'] / total_attempts * 100) if total_attempts else 0
            avg_latency = (sum(self.metrics['api_latency']) / len(self.metrics['api_latency'])
                           if self.metrics['api_latency'] else 0)

            logger.info(f"Echochambers Metrics:"
                        f"\n- Success Rate: {success_rate:.2f}%"
                        f"\n- Average Latency: {avg_latency:.2f} ms"
                        f"\n- Messages Sent: {self.metrics['messages_sent']}"
                        f"\n- Messages Failed: {self.metrics['messages_failed']}"
                        f"\n- Last Error: {self.metrics['last_error']}")

            self.metrics['last_metrics_log'] = current_time

    def configure(self) -> bool:
        """Configure the Echochambers connection"""
        logger.info("Configuring Echochambers connection")
        try:
            # Test the connection by making a simple request
            self.get_room_info()
            logger.info("Successfully configured Echochambers connection")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Echochambers connection: {str(e)}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if the connection is properly configured"""
        essentials = [self.api_url, self.api_key, self.room, self.sender_username, self.sender_model]
        if not all(essentials):
            if verbose:
                logger.info("Echochambers connection is not configured")
            return False

        try:
            # Test connection by making a simple request
            self.get_room_info()
            if verbose:
                logger.info("Echochambers connection is configured and working")
            return True
        except Exception as e:
            if verbose:
                logger.error(f"Echochambers connection test failed: {str(e)}")
            return False

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute an Echochambers action with validation"""
        action = self.actions.get(action_name)
        if not action:
            raise KeyError(f"Unknown action: {action_name}")

        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name, None)
        if method:
            return method(**kwargs)
        else:
            raise NotImplementedError(f"The action '{action_name}' is not implemented.")