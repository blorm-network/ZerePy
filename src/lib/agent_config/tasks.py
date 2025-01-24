from pydantic import BaseModel


class Task(BaseModel):
    weight: int
    min_interval: int
    max_interval: int


class Tasks(BaseModel):
    post_tweet: Task
    reply_to_tweet: Task
    like_tweet: Task
