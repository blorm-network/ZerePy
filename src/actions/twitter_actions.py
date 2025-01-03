import time 
from src.action_handler import register_action
from src.helpers import print_h_bar


@register_action("post-tweet")
def post_tweet(agent, **kwargs):
    current_time = time.time()

    if ("last_tweet_time" not in agent.state):
        last_tweet_time = 0

    if current_time - last_tweet_time >= agent.tweet_interval:
        agent.logger.info("\n📝 GENERATING NEW TWEET")
        print_h_bar()
        prompt = ("Generate an engaging tweet. Don't include any hashtags, links or emojis. Keep it under 280 characters."
                f"The tweets should be pure commentary, do not shill any coins or projects apart from {agent.name}. Do not repeat any of the"
                "tweets that were given as example. Avoid the words AI and crypto.")
        tweet_text = agent.prompt_llm(prompt)

        if tweet_text:
            agent.logger.info("\n🚀 Posting tweet:")
            agent.logger.info(f"'{tweet_text}'")
            agent.connection_manager.perform_action(
                connection_name="twitter",
                action_name="post-tweet",
                params=[tweet_text]
            )
            agent.state["last_tweet_time"] = current_time
            agent.logger.info("\n✅ Tweet posted successfully!")
            return True
    else:
        agent.logger.info("\n👀 Delaying post until tweet interval elapses...")
        return False


@register_action("reply-to-tweet")
def reply_to_tweet(agent, **kwargs):
    if "timeline_tweets" in agent.state and agent.state["timeline_tweets"] is not None and len(agent.state["timeline_tweets"]) > 0:
        tweet = agent.state["timeline_tweets"].pop(0)
        tweet_id = tweet.get('id')
        if not tweet_id:
            return

        agent.logger.info(f"\n💬 GENERATING REPLY to: {tweet.get('text', '')[:50]}...")

        base_prompt = (f"Generate a friendly, engaging reply to this tweet: {tweet.get('text')}. Keep it under 280 characters. Don't include any usernames, hashtags, links or emojis. ")
        system_prompt = agent._construct_system_prompt()
        reply_text = agent.prompt_llm(prompt=base_prompt, system_prompt=system_prompt)

        if reply_text:
            agent.logger.info(f"\n🚀 Posting reply: '{reply_text}'")
            agent.connection_manager.perform_action(
                connection_name="twitter",
                action_name="reply-to-tweet",
                params=[tweet_id, reply_text]
            )
            agent.logger.info("✅ Reply posted successfully!")
            return True
    else:
        agent.logger.info("\n👀 No tweets found to reply to...")
        return False

@register_action("like-tweet")
def like_tweet(agent, **kwargs):
    if "timeline_tweets" in agent.state and agent.state["timeline_tweets"] is not None and len(agent.state["timeline_tweets"]) > 0:
        tweet = agent.state["timeline_tweets"].pop(0)
        tweet_id = tweet.get('id')
        if not tweet_id:
            return False

        agent.logger.info(f"\n👍 LIKING TWEET: {tweet.get('text', '')[:50]}...")

        agent.connection_manager.perform_action(
            connection_name="twitter",
            action_name="like-tweet",
            params=[tweet_id]
        )
        agent.logger.info("✅ Tweet liked successfully!")
        return True
    else:
        agent.logger.info("\n👀 No tweets found to like...")
    return False