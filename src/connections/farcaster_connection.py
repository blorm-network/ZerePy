import os
import logging
from typing import Dict, Any, List, Optional, cast
from dotenv import set_key, load_dotenv
from farcaster import Warpcast
from farcaster.models import CastContent, CastHash, IterableCastsResult, Parent, ReactionsPutResult
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.types.connections import FarcasterConfig
from src.types.config import BaseConnectionConfig

logger = logging.getLogger("connections.farcaster_connection")

class FarcasterConnectionError(Exception):
    """Base exception for Farcaster connection errors"""
    pass

class FarcasterConfigurationError(FarcasterConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class FarcasterAPIError(FarcasterConnectionError):
    """Raised when Farcaster API requests fail"""
    pass

class FarcasterConnection(BaseConnection):
    _client: Optional[Warpcast]
    
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Farcaster connection...")
        # Validate config before passing to super
        validated_config = FarcasterConfig(**config)
        super().__init__(validated_config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> BaseConnectionConfig:
        """Validate Farcaster configuration from JSON and convert to Pydantic model"""
        try:
            # Convert dict config to Pydantic model
            validated_config = FarcasterConfig(**config)
            return validated_config
        except Exception as e:
            raise ValueError(f"Invalid Farcaster configuration: {str(e)}")

    def register_actions(self) -> None:
        """Register available Farcaster actions"""
        self.actions = {
            "get-latest-casts": Action(
                name="get-latest-casts",
                method=self.get_latest_casts,
                parameters=[
                    ActionParameter("fid", True, int, "Farcaster ID of the user"),
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read, defaults to 25")
                ],
                description="Get the latest casts from a user"
            ),
            "post-cast": Action(
                name="post-cast",
                method=self.post_cast,
                parameters=[
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel key, defaults to None")
                ],
                description="Post a new cast"
            ),
            "read-timeline": Action(
                name="read-timeline",
                method=self.read_timeline,
                parameters=[
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read, defaults to 100")
                ],
                description="Read all recent casts"
            ),
            "like-cast": Action(
                name="like-cast",
                method=self.like_cast,
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to like")
                ],
                description="Like a specific cast"
            ),
            "requote-cast": Action(
                name="requote-cast",
                method=self.requote_cast,
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to requote")
                ],
                description="Requote a cast (recast)"
            ),
            "reply-to-cast": Action(
                name="reply-to-cast",
                method=self.reply_to_cast,
                parameters=[
                    ActionParameter("parent_fid", True, int, "Farcaster ID of the parent cast to reply to"),
                    ActionParameter("parent_hash", True, str, "Hash of the parent cast to reply to"),
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel key, defaults to None")
                ],
                description="Reply to a cast"
            ),
            "get-cast-replies": Action(
                name="get-cast-replies",
                method=self.get_cast_replies,
                parameters=[
                    ActionParameter("thread_hash", True, str, "Hash of the thread to query for replies")
                ],
                description="Fetch cast replies (thread)"
            )
        }
    
    def _get_credentials(self) -> Dict[str, str]:
        """Get Farcaster credentials from environment with validation"""
        logger.debug("Retrieving Farcaster credentials")
        load_dotenv()

        required_vars = {
            'FARCASTER_MNEMONIC': 'recovery phrase',
        }

        credentials: Dict[str, str] = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            else:
                credentials[env_var] = value

        if missing:
            error_msg = f"Missing Farcaster credentials: {', '.join(missing)}"
            raise FarcasterConfigurationError(error_msg)

        logger.debug("All required credentials found")
        return credentials

    def configure(self, **kwargs: Any) -> bool:
        """Sets up Farcaster bot authentication"""
        logger.info("\nStarting Farcaster authentication setup")

        if self.is_configured():
            logger.info("Farcaster is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your Farcaster (Warpcast) recovery phrase (for connection):")
        logger.info("1. Open the Warpcast mobile app")
        logger.info("2. Navigate to Settings page (click profile picture on top left, then the gear icon on top right)")
        logger.info("3. Click 'Advanced' then 'Reveal recovery phrase'")
        logger.info("4. Copy your recovery phrase")

        recovery_phrase = input("\nEnter your Farcaster (Warpcast) recovery phrase: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            logger.info("Saving recovery phrase to .env file...")
            set_key('.env', 'FARCASTER_MNEMONIC', recovery_phrase)

            # Simple validation of token format
            if not recovery_phrase.strip():
                logger.error("❌ Invalid recovery phrase format")
                return False

            logger.info("✅ Farcaster (Warpcast) configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"❌ Configuration failed: {e}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Farcaster credentials are configured and valid"""
        logger.debug("Checking Farcaster configuration status")
        try:
            credentials = self._get_credentials()

            self._client = Warpcast(mnemonic=credentials['FARCASTER_MNEMONIC'])
            if self._client is None:
                return False

            self._client.get_me()
            logger.debug("Farcaster configuration is valid")
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, FarcasterConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, FarcasterAPIError):
                    error_msg = f"API validation error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False
    
    def perform_action(self, action_name: str, **kwargs: Any) -> Any:
        """Execute an action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        # Add config parameters if not provided
        if action_name == "read-timeline" and "count" not in kwargs:
            config = cast(FarcasterConfig, self.config)
            kwargs["count"] = config.timeline_read_count

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
    
    def get_latest_casts(self, fid: int, cursor: Optional[str] = None, limit: int = 25) -> IterableCastsResult:
        """Get the latest casts from a user"""
        logger.debug(f"Getting latest casts for {fid}, cursor: {cursor}, limit: {limit}")

        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")

        casts = self._client.get_casts(fid, cursor, limit)
        if not isinstance(casts, IterableCastsResult):
            raise FarcasterAPIError("Unexpected response type")
        return casts

    def post_cast(self, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Post a new cast"""
        logger.debug(f"Posting cast: {text}, embeds: {embeds}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        return self._client.post_cast(text, embeds, None, channel_key)


    def read_timeline(self, cursor: Optional[str] = None, limit: int = 100) -> IterableCastsResult:
        """Read all recent casts"""
        logger.debug(f"Reading timeline, cursor: {cursor}, limit: {limit}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        casts = self._client.get_recent_casts(cursor, limit)
        if not isinstance(casts, IterableCastsResult):
            raise FarcasterAPIError("Unexpected response type")
        return casts

    def like_cast(self, cast_hash: str) -> ReactionsPutResult:
        """Like a specific cast"""
        logger.debug(f"Liking cast: {cast_hash}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        return self._client.like_cast(cast_hash)
    
    def requote_cast(self, cast_hash: str) -> CastHash:
        """Requote a cast (recast)"""
        logger.debug(f"Requoting cast: {cast_hash}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        return self._client.recast(cast_hash)

    def reply_to_cast(self, parent_fid: int, parent_hash: str, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Reply to an existing cast"""
        logger.debug(f"Replying to cast: {parent_hash}, text: {text}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        parent = Parent(fid=parent_fid, hash=parent_hash)
        return self._client.post_cast(text, embeds, parent, channel_key)
    
    def get_cast_replies(self, thread_hash: str) -> IterableCastsResult:
        """Fetch cast replies (thread)"""
        logger.debug(f"Fetching replies for thread: {thread_hash}")
        if self._client is None:
            raise FarcasterConnectionError("Client not initialized")
        casts = self._client.get_all_casts_in_thread(thread_hash)
        if not isinstance(casts, IterableCastsResult):
            raise FarcasterAPIError("Unexpected response type")
        return casts
    
    # "reply-to-cast": Action(
    #     name="reply-to-cast",
    #     parameters=[
    #         ActionParameter("parent_fid", True, int, "Farcaster ID of the parent cast to reply to"),
    #         ActionParameter("parent_hash", True, str, "Hash of the parent cast to reply to"),
    #         ActionParameter("text", True, str, "Text content of the cast"),
    #     ],
    #     description="Reply to an existing cast"
    # ),
    # "get-cast-replies": Action(
    #     name="get-cast-replies", # get_all_casts_in_thread
    #     parameters=[
    #         ActionParameter("thread_hash", True, str, "Hash of the thread to query for replies")
    #     ],
    #     description="Fetch cast replies (thread)"
    # )
