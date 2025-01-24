from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class TwitterSettings(BaseSettings):
    consumer_key: str = Field(validation_alias="TWITTER_CONSUMER_KEY")
    consumer_secret: str = Field(validation_alias="TWITTER_CONSUMER_SECRET")
    access_token: str = Field(validation_alias="TWITTER_ACCESS_TOKEN")
    access_token_secret: str = Field(validation_alias="TWITTER_ACCESS_TOKEN_SECRET")
    user_id: str = Field(validation_alias="TWITTER_USER_ID")


class TwitterConfig(BaseModel):
    timeline_read_count: int
    own_tweet_replies_count: int
    tweet_interval: int
    twitter_settings: TwitterSettings

    def __init__(self, **data) -> None:
        # if the connection is not configured, return none
        try:
            data["twitter_settings"] = TwitterSettings()
            super().__init__(**data)
        except Exception as e:
            return
