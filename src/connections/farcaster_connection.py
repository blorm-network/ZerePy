import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import set_key, load_dotenv
from farcaster import Warpcast
from farcaster.models import CastContent, CastHash, IterableCastsResult, Parent, ReactionsPutResult
from src.connections.base_connection import BaseConnection, Action, ActionParameter

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
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing Farcaster connection...")
        super().__init__(config)
        self._client: Warpcast = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Farcaster configuration from JSON"""
        required_fields = ["timeline_read_count", "cast_interval"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["timeline_read_count"], int) or config["timeline_read_count"] <= 0:
            raise ValueError("timeline_read_count must be a positive integer")

        if not isinstance(config["cast_interval"], int) or config["cast_interval"] <= 0:
            raise ValueError("cast_interval must be a positive integer")
            
        return config

    def register_actions(self) -> None:
        """Register available Farcaster actions"""
        self.actions = {
            "get-latest-casts": Action(
                name="get-latest-casts",
                parameters=[
                    ActionParameter("fid", True, int, "Farcaster ID of the user"),
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read, defaults to 25, otherwise min(limit, 100)")
                ],
                description="Get the latest casts from a user"
            ),
            "post-cast": Action(
                name="post-cast",
                parameters=[
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel key, defaults to None"),
                ],
                description="Post a new cast"
            ),
            "read-timeline": Action(
                name="read-timeline",
                parameters=[
                    ActionParameter("cursor", False, int, "Cursor, defaults to None"),
                    ActionParameter("limit", False, int, "Number of casts to read from timeline, defaults to 100")
                ],
                description="Read all recent casts"
            ),
            "like-cast": Action(
                name="like-cast",
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to like")
                ],
                description="Like a specific cast"
            ),
            "requote-cast": Action(
                name="requote-cast",
                parameters=[
                    ActionParameter("cast_hash", True, str, "Hash of the cast to requote")
                ],
                description="Requote a cast (recast)"
            ),
            "reply-to-cast": Action(
                name="reply-to-cast",
                parameters=[
                    ActionParameter("parent_fid", True, int, "Farcaster ID of the parent cast to reply to"),
                    ActionParameter("parent_hash", True, str, "Hash of the parent cast to reply to"),
                    ActionParameter("text", True, str, "Text content of the cast"),
                    ActionParameter("embeds", False, List[str], "List of embeds, defaults to None"),
                    ActionParameter("channel_key", False, str, "Channel of the cast, defaults to None"),
                ],
                description="Reply to a cast"
            ),
            "get-cast-replies": Action(
                name="get-cast-replies", # get_all_casts_in_thread
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

        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing Farcaster credentials: {', '.join(missing)}"
            raise FarcasterConfigurationError(error_msg)

        logger.debug("All required credentials found")
        return credentials

    def configure(self) -> bool:
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

    def is_configured(self, verbose = False) -> bool:
        """Check if Farcaster credentials are configured and valid"""
        logger.debug("Checking Farcaster configuration status")
        try:
            credentials = self._get_credentials()

            self._client = Warpcast(mnemonic=credentials['FARCASTER_MNEMONIC'])

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
    
    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Farcaster action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Add config parameters if not provided
        if action_name == "read-timeline" and "count" not in kwargs:
            kwargs["count"] = self.config["timeline_read_count"]

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
    
    def get_latest_casts(self, fid: int, cursor: Optional[int] = None, limit: Optional[int] = 25) -> IterableCastsResult:
        """Get the latest casts from a user"""
        logger.debug(f"Getting latest casts for {fid}, cursor: {cursor}, limit: {limit}")

        casts = self._client.get_casts(fid, cursor, limit)
        logger.debug(f"Retrieved {len(casts)} casts")
        return casts

    def post_cast(self, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Post a new cast"""
        logger.debug(f"Posting cast: {text}, embeds: {embeds}")
        return self._client.post_cast(text, embeds, None, channel_key)


    def read_timeline(self, cursor: Optional[int] = None, limit: Optional[int] = 100) -> IterableCastsResult:
        """Read all recent casts"""
        logger.debug(f"Reading timeline, cursor: {cursor}, limit: {limit}")
        return self._client.get_recent_casts(cursor, limit)

    def like_cast(self, cast_hash: str) -> ReactionsPutResult:
        """Like a specific cast"""
        logger.debug(f"Liking cast: {cast_hash}")
        return self._client.like_cast(cast_hash)
    
    def requote_cast(self, cast_hash: str) -> CastHash:
        """Requote a cast (recast)"""
        logger.debug(f"Requoting cast: {cast_hash}")
        return self._client.recast(cast_hash)

    def reply_to_cast(self, parent_fid: int, parent_hash: str, text: str, embeds: Optional[List[str]] = None, channel_key: Optional[str] = None) -> CastContent:
        """Reply to an existing cast"""
        logger.debug(f"Replying to cast: {parent_hash}, text: {text}")
        parent = Parent(fid=parent_fid, hash=parent_hash)
        return self._client.post_cast(text, embeds, parent, channel_key)
    
    def get_cast_replies(self, thread_hash: str) -> IterableCastsResult:
        """Fetch cast replies (thread)"""
        logger.debug(f"Fetching replies for thread: {thread_hash}")
        return self._client.get_all_casts_in_thread(thread_hash)
    
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
