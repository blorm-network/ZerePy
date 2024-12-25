import tweepy
import requests
import tempfile
import os
import logging
from typing import Dict, List, Optional

class TwitterService:
    def __init__(self, api_client):
        self.client = api_client
        self.logger = logging.getLogger(__name__)

    async def post_with_media(self, content: Dict) -> bool:
        """Post tweet with optional media"""
        try:
            if 'media' in content and content['media']:
                # Process and upload media
                media_ids = await self._process_media(content['media'])
                
                if media_ids:
                    # Post tweet with media
                    self.client.create_tweet(
                        text=content['text'],
                        media_ids=media_ids
                    )
                    self.logger.info("Posted tweet with media")
                else:
                    # Fallback to text-only if media processing failed
                    self.client.create_tweet(text=content['text'])
                    self.logger.warning("Posted text-only due to media processing failure")
            else:
                # Regular text tweet
                self.client.create_tweet(text=content['text'])
                self.logger.info("Posted text-only tweet")
                
            return True

        except Exception as e:
            self.logger.error(f"Failed to post tweet: {e}")
            return False

    async def _process_media(self, media_url: str) -> Optional[List[str]]:
        """Download and upload media to Twitter"""
        try:
            media_ids = []
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                # Download image
                response = requests.get(media_url)
                if response.status_code != 200:
                    raise Exception("Failed to download image")
                    
                tmp_file.write(response.content)
                tmp_file.flush()
                
                # Upload to Twitter
                with open(tmp_file.name, 'rb') as media_file:
                    media = self.client.media_upload(filename=tmp_file.name)
                    media_ids.append(media.media_id)
                    
            # Cleanup
            os.unlink(tmp_file.name)
            return media_ids

        except Exception as e:
            self.logger.error(f"Media processing failed: {e}")
            return None

    async def _get_context(self) -> Optional[str]:
        """Get context from timeline/mentions"""
        try:
            # Get recent mentions
            mentions = self.client.get_mentions_timeline(
                count=5,
                tweet_mode="extended"
            )
            
            if mentions:
                # Process most recent mention
                latest_mention = mentions[0]
                return latest_mention.full_text
                
            return None

        except Exception as e:
            self.logger.error(f"Failed to get context: {e}")
            return None 