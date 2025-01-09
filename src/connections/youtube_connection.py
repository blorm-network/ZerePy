import os
import logging
import threading
import time
from typing import Dict, Any, List
import wsgiref.simple_server

# Google API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Local imports
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.prompts import REPLY_YOUTUBE_PROMPT
from src.helpers import print_h_bar

# Configure logging
logger = logging.getLogger("connections.youtube_connection")
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

class YouTubeConnectionError(Exception):
    """Base exception for YouTube connection errors"""
    pass

class YouTubeConfigurationError(YouTubeConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class YouTubeAPIError(YouTubeConnectionError):
    """Raised when YouTube API requests fail"""
    pass

class YouTubeConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        self._youtube = None
        self._credentials = None
        super().__init__(config)

    @property
    def is_llm_provider(self) -> bool:
        return False
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration parameters for YouTube connection"""
        required_fields = ["comment_fetch_count"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
        
        if not isinstance(config["comment_fetch_count"], int) or config["comment_fetch_count"] <= 0:
            raise ValueError("comment_fetch_count must be a positive integer")
            
        return config
    
    def register_actions(self) -> None:
        """Register available YouTube actions"""
        self.actions = {
            "get-recent-comments": Action(
                name="get-recent-comments",
                parameters=[
                    ActionParameter("count", False, int, "Number of comments to retrieve")
                ],
                description="Get recent comments from your channel's videos"
            ),
            "reply-to-comment": Action(
                name="reply-to-comment",
                parameters=[
                    ActionParameter("comment_id", True, str, "ID of the comment to reply to"),
                ],
                description="Generate and post a reply to a specific YouTube comment"
            ),
            "start-bot": Action(
                name="start-bot",
                parameters=[],
                description="Start monitoring your channel's comments and replying autonomously"
            ),
            "stop-bot": Action(
                name="stop-bot",
                parameters=[],
                description="Stop monitoring comments"
            )
        }

    def configure(self) -> bool:
        """Sets up YouTube API authentication"""
        logger.info("Starting YouTube API setup")

        if self.is_configured(verbose=False):
            logger.info("YouTube API is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        setup_instructions = [
            "\n📺 YOUTUBE API SETUP",
            "\n📝 To get your YouTube API credentials:",
            "1. Go to https://developers.google.com/youtube/v3/getting-started",
            "2. Create an external app, enable the YouTube Data API v3, add yourself as a test user",
            "3. Create credentials:",
            "   - API key for fetching comments",
            "   - OAuth 2.0 Client ID and Secret for posting replies",
            "4. Enter these credentials in the following steps"
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        try:
            api_key = input("Enter your API Key: ")
            client_id = input("Enter your OAuth Client ID: ")
            client_secret = input("Enter your OAuth Client Secret: ")

            # Suppress default server logging
            class NoOutputServerHandler(wsgiref.simple_server.WSGIRequestHandler):
                def log_message(self, format, *args):
                    pass

            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uris": ["http://localhost"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
            )
            
            print("\n5. Almost done...")
            
            # Set up and run local server without browser opening
            wsgiref.simple_server.WSGIRequestHandler = NoOutputServerHandler
            credentials = flow.run_local_server(port=0, open_browser=False)
    
            env_vars = {
                'YOUTUBE_API_KEY': api_key,
                'YOUTUBE_CLIENT_ID': client_id,
                'YOUTUBE_CLIENT_SECRET': client_secret,
                'YOUTUBE_REFRESH_TOKEN': credentials.refresh_token
            }

            if not os.path.exists('.env'):
                logger.debug("Creating new .env file")
                with open('.env', 'w') as f:
                    f.write('')

            for key, value in env_vars.items():
                set_key('.env', key, value)
                logger.debug(f"Saved {key} to .env")

            logger.info("\n✅ YouTube API configuration successful!")
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            raise YouTubeConfigurationError(error_msg)

    def is_configured(self, verbose=False) -> bool:
        """Check if YouTube credentials are configured and valid"""
        logger.debug("Checking YouTube configuration status")
        try:
            credentials = self._get_credentials()
            youtube = build('youtube', 'v3', developerKey=credentials['YOUTUBE_API_KEY'])
            
            # Verify API key by attempting to fetch a public channel
            youtube.channels().list(
                part='snippet',
                id='UC_x5XG1OV2P6uZZ5FSM9Ttw'  # Google Developers channel
            ).execute()

            self._refresh_oauth_credentials()
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, YouTubeConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, YouTubeAPIError):
                    error_msg = f"API validation error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False

    def get_recent_comments(self, count: int = None, **kwargs) -> list:
        """Get recent comments from all videos in your YouTube channel"""
        if count is None:
            count = self.config["comment_fetch_count"]
        logger.info(f"\n👀 Fetching {count} most recent new comments...")

        try:
            if not self._youtube:
                credentials = self._get_credentials()
                self._youtube = build('youtube', 'v3', developerKey=credentials['YOUTUBE_API_KEY'])

            channel_id = self._get_bot_channel_id()
            if not channel_id:
                logger.error("Could not get channel ID")
                return []

            # Fetch comments page by page until we have enough or run out
            comments = []
            next_page_token = None
            
            while True:
                response = self._youtube.commentThreads().list(
                    part='snippet,replies',
                    allThreadsRelatedToChannelId=channel_id,
                    maxResults=count,
                    pageToken=next_page_token,
                    order='time',
                ).execute()

                for item in response.get('items', []):
                    comment = item['snippet']['topLevelComment']
                    comment_author_id = comment['snippet']['authorChannelId']['value']
                    
                    # Process top-level comment if it's not from the bot
                    if comment_author_id != channel_id:
                        # Check if the bot has already replied to this comment
                        has_bot_reply = False
                        if 'replies' in item:
                            has_bot_reply = any(
                                reply['snippet']['authorChannelId']['value'] == channel_id
                                for reply in item['replies']['comments']
                            )

                        if not has_bot_reply:
                            comment_data = {
                                'id': item['id'],
                                'text': comment['snippet']['textDisplay'],
                                'author': comment['snippet']['authorDisplayName'],
                                'like_count': comment['snippet']['likeCount'],
                                'video_id': item['snippet']['videoId'],
                                'is_reply': False
                            }
                            comments.append(comment_data)

                    # Process replies
                    if 'replies' in item:
                        replies = item['replies']['comments']
                        for i, reply in enumerate(replies):
                            reply_author_id = reply['snippet']['authorChannelId']['value']
                            
                            # Skip if this is the bot's reply
                            if reply_author_id == channel_id:
                                continue
                                
                            # Check if this reply is responding to the bot's comment
                            is_reply_to_bot = False
                            if i > 0:  # Check previous replies
                                prev_reply = replies[i - 1]
                                if prev_reply['snippet']['authorChannelId']['value'] == channel_id:
                                    is_reply_to_bot = True
                            
                            # Only include replies that are responding to the bot and haven't been replied to
                            if is_reply_to_bot:
                                has_bot_response = False
                                # Check if bot has responded to this reply
                                for subsequent_reply in replies[i + 1:]:
                                    if subsequent_reply['snippet']['authorChannelId']['value'] == channel_id:
                                        has_bot_response = True
                                        break
                                
                                if not has_bot_response:
                                    reply_data = {
                                        'id': reply['id'],
                                        'text': reply['snippet']['textDisplay'],
                                        'author': reply['snippet']['authorDisplayName'],
                                        'parent_id': item['id'],
                                        'is_reply': True
                                    }
                                    comments.append(reply_data)

                next_page_token = response.get('nextPageToken')
                if not next_page_token or len(comments) >= count:
                    break

            if not comments:
                logger.info("No new comments found")
            else:
                logger.info(f"\n✅ Found {len(comments)} new comments to process")
            return comments

        except Exception as e:
            error_msg = f"Failed to get comments: {str(e)}"
            logger.error(error_msg)
            raise YouTubeAPIError(error_msg)
        
    def reply_to_comment(self, comment_id: str, system_prompt: str = "", **kwargs):
        """Post a reply to a specific comment."""
        try:
            # Get system prompt and comment details
            system_prompt = self.connection_manager.parent_agent._construct_system_prompt()
            comment = self.get_comment_details(comment_id)
            if not comment:
                raise YouTubeAPIError("Could not get comment details")
                
            # Skip replies to replies
            if comment.get('is_reply'):
                logger.info(f"Skipping reply to @{comment['author']}'s comment - YouTube API doesn't support replying to replies")
                return None
                
            logger.info(f"💭 Processing comment from {comment['author']}: '{comment['text']}'")
            
            # Generate response
            captions = self.get_video_captions(comment["video_id"])
            prompt = REPLY_YOUTUBE_PROMPT.format(
                context=captions if captions else "No captions available",
                author=comment["author"],
                comment_text=comment["text"]
            )
            response = self.connection_manager.perform_action(
                connection_name=self.connection_manager.get_model_providers()[0],
                action_name="generate-text",
                params=[prompt, system_prompt]
            )
            
            # Post reply with fresh credentials
            logger.info(f"🚀 Posting reply: '{response}'")
            credentials = self._get_credentials()
            creds = Credentials(
                token=None,
                refresh_token=credentials['YOUTUBE_REFRESH_TOKEN'],
                token_uri='https://oauth2.googleapis.com/token',
                client_id=credentials['YOUTUBE_CLIENT_ID'],
                client_secret=credentials['YOUTUBE_CLIENT_SECRET'],
                scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
            )
            creds.refresh(Request())
            
            youtube = build('youtube', 'v3', credentials=creds)
            channel_id = self._get_bot_channel_id()
            
            result = youtube.comments().insert(
                part='snippet',
                body={
                    'snippet': {
                        'parentId': comment_id,
                        'textOriginal': response,
                        'channelId': channel_id
                    }
                }
            ).execute()
            
            logger.info("✅ Reply posted successfully!")
            return None

        except Exception as e:
            logger.error(f"Failed to post YouTube comment reply: {e}")
            raise YouTubeAPIError(f"Error in reply_to_comment: {e}")
    
    def start_bot(self, **kwargs) -> None:
        """Start monitoring YouTube comments and replying autonomously"""
        if hasattr(self, '_polling_thread') and self._polling_thread and self._polling_thread.is_alive():
            logger.info("Bot is already running")
            return False

        try:
            logger.info("\n🚀 Starting YouTube comment bot...")
            def poll_comments():
                while hasattr(self, '_running') and self._running:
                    try:
                        logger.info("\n👀 Checking for new YouTube comments...")
                        comments = self.get_recent_comments()
                        
                        if comments:
                            for comment in comments:
                                self.reply_to_comment(comment['id'])
                        
                        logger.info("\n⏳ Waiting 60 seconds before next check...")
                        time.sleep(60)
                    except Exception as e:
                        logger.error(f"Error in comment polling: {e}")
                        time.sleep(60)

            self._running = True
            self._polling_thread = threading.Thread(target=poll_comments, daemon=True)
            self._polling_thread.start()
            logger.info("✅ Bot started successfully!")
            return True

        except Exception as e:
            self._running = False
            logger.error(f"Failed to start bot: {e}")
            return False

    def stop_bot(self, **kwargs) -> None:
            """Stop the YouTube comment bot"""
            if not hasattr(self, '_running') or not self._running:
                logger.warning("Bot is not running")
                return False

            self._running = False
            if hasattr(self, '_polling_thread'):
                self._polling_thread = None
            logger.info("✅ Bot stopped successfully!")
            return True
        
    def get_comment_details(self, comment_id: str) -> Dict[str, Any]:
        """Get full details of a specific comment"""
        try:
            if not self._youtube:
                credentials = self._get_credentials()
                self._youtube = build('youtube', 'v3', developerKey=credentials['YOUTUBE_API_KEY'])

            try:
                response = self._youtube.commentThreads().list(
                    part='snippet',
                    id=comment_id
                ).execute()

                if response.get('items'):
                    comment = response['items'][0]['snippet']['topLevelComment']
                    is_reply = False
                else:
                    response = self._youtube.comments().list(
                        part='snippet',
                        id=comment_id
                    ).execute()

                    if not response.get('items'):
                        logger.error(f"No comment found with ID: {comment_id}")
                        return None

                    comment = response['items'][0]
                    is_reply = True

                return {
                    'id': comment_id,
                    'text': comment['snippet']['textDisplay'],
                    'author': comment['snippet']['authorDisplayName'],
                    'video_id': comment['snippet']['videoId'],
                    'is_reply': is_reply
                }

            except HttpError as e:
                logger.error(f"Failed to retrieve comment details: {e}")
                return None

        except Exception as e:
            logger.error(f"Failed to get comment details: {e}")
            return None

    def get_video_captions(self, video_id: str) -> str:
        """Get captions for a specific video"""
        try:
            self._refresh_oauth_credentials()
            youtube_oauth = build('youtube', 'v3', credentials=self._credentials)

            captions_list = youtube_oauth.captions().list(
                part="snippet",
                videoId=video_id
            ).execute()

            caption_id = None
            for item in captions_list.get('items', []):
                if item['snippet']['language'] == 'en':
                    caption_id = item['id']
                    break
            
            if not caption_id:
                logger.debug(f"No English captions found for video {video_id}")
                return None

            caption_request = youtube_oauth.captions().download(
                id=caption_id,
                tfmt='srt'
            )
            caption_response = caption_request.execute()
            if isinstance(caption_response, bytes):
                caption_text = caption_response.decode('utf-8')
            else:
                caption_text = str(caption_response)

            return self._preprocess_captions(caption_text)

        except Exception as e:
            logger.error(f"Failed to get captions for video {video_id}: {e}")
            return None

    def _preprocess_captions(self, captions: str) -> str:
        """Clean up SRT formatted captions"""
        if not captions:
            return None

        try:
            # Split into lines
            lines = captions.split('\n')
            
            # Remove timestamp lines (contain ' --> '), numeric counter lines, empty lines
            clean_lines = []
            for line in lines:
                if '-->' not in line and not line.strip().isdigit() and line.strip():
                    clean_lines.append(line.strip())
                    
            # Join back together
            clean_captions = ' '.join(clean_lines)
            
            # Log first bit of processed captions
            preview = clean_captions[:100] + '...' if len(clean_captions) > 100 else clean_captions
            logger.info(f"📝 Getting captions for context: '{preview}'")
            
            return clean_captions

        except Exception as e:
            logger.error(f"Failed to process captions: {e}")
            return None

    def _get_credentials(self) -> Dict[str, str]:
        """Get YouTube API credentials from environment with validation"""
        load_dotenv()

        required_vars = {
            'YOUTUBE_API_KEY': 'API key',
            'YOUTUBE_CLIENT_ID': 'client ID',
            'YOUTUBE_CLIENT_SECRET': 'client secret',
            'YOUTUBE_REFRESH_TOKEN': 'refresh token'
        }

        credentials = {}
        missing = []

        for env_var, description in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing.append(description)
            credentials[env_var] = value

        if missing:
            error_msg = f"Missing YouTube credentials: {', '.join(missing)}"
            raise YouTubeConfigurationError(error_msg)

        return credentials

    def _refresh_oauth_credentials(self):
        """Refresh OAuth credentials if expired"""
        try:
            credentials = self._get_credentials()
            
            creds = Credentials(
                None,
                refresh_token=credentials['YOUTUBE_REFRESH_TOKEN'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=credentials['YOUTUBE_CLIENT_ID'],
                client_secret=credentials['YOUTUBE_CLIENT_SECRET']
            )

            if not creds.valid:
                creds.refresh(Request())
            
            self._credentials = creds
            
        except Exception as e:
            raise YouTubeConfigurationError(f"Failed to refresh credentials: {str(e)}")
        
    def _get_bot_channel_id(self):
        """Get the bot's YouTube channel ID using OAuth credentials"""
        try:
            self._refresh_oauth_credentials()
            temp_youtube = build('youtube', 'v3', credentials=self._credentials)
            
            response = temp_youtube.channels().list(
                part='id',
                mine=True
            ).execute()
            
            if response.get('items'):
                channel_id = response['items'][0]['id']
                return channel_id
            return None
            
        except Exception as e:
            logger.error(f"Failed to get bot channel ID: {e}")
            return None

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a YouTube action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        logger.debug(f"Required params: {[p.name for p in action.parameters if p.required]}")
        
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)