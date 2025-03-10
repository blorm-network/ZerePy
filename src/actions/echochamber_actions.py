import time,random
import logging
from src.action_handler import register_action
from src.prompts import REPLY_ECHOCHAMBER_PROMPT, POST_ECHOCHAMBER_PROMPT

logger = logging.getLogger("action_handler")

@register_action("post-echochambers")
def post_echochambers(agent, **kwargs):
    current_time = time.time()

    # Initialize context
    if "echochambers_last_message" not in agent.context:
        agent.context["echochambers_last_message"] = 0
    if "echochambers_replied_messages" not in agent.context:
        agent.context["echochambers_replied_messages"] = set()
    
    if current_time - agent.context["echochambers_last_message"] > agent.echochambers_message_interval:
        logger.info("\n📝 GENERATING NEW ECHOCHAMBERS MESSAGE")
        
        # Generate message based on room topic and tags
        previous_messages = agent.connection_manager.connections["echochambers"].sent_messages
        previous_content = "\n".join([f"- {msg['content']}" for msg in previous_messages])
        logger.info(f"Found {len(previous_messages)} messages in post history")
        
        prompt  = POST_ECHOCHAMBER_PROMPT.format(
            room_topic=agent.context['room_info']['topic'],
            tags=", ".join(agent.context['room_info']['tags']),
            previous_content=previous_content
        )
        message = agent.prompt_llm(prompt)
        
        if message:
            agent.logger.info(f"\n🚀 Posting message: '{message[:69]}...'")
            agent.connection_manager.perform_action(
                connection_name="echochambers",
                action_name="send-message",
                params=[message]  # Pass as list of values
            )
            agent.context["echochambers_last_message"] = current_time
            agent.logger.info("✅ Message posted successfully!")
            return True
    return False

@register_action("reply-echochambers")
def reply_echochambers(agent, **kwargs):
    agent.logger.info("\n🔍 CHECKING FOR MESSAGES TO REPLY TO")
    
    # Initialize replied messages set if not exists
    if "echochambers_replied_messages" not in agent.context:
        agent.context["echochambers_replied_messages"] = set()
        

    # Get recent messages
    history = agent.connection_manager.perform_action(
        connection_name="echochambers",
        action_name="get-room-history",
        params={}
    )

    if history:
        agent.logger.info(f"Found {len(history)} messages in history")
        for message in history:
            message_id = message.get('id')
            sender = message.get('sender', {})
            sender_username = sender.get('username')
            content = message.get('content', '')
            
            if not message_id or not sender_username or not content:
                agent.logger.warning(f"Skipping message with missing fields: {message}")
                continue
            

            # Skip if:
            # 1. It's our message
            # 2. We've already replied to it
            if (sender_username == agent.connection_manager.connections["echochambers"].config["sender_username"] or 
                message_id in agent.context.get("echochambers_replied_messages", set())):
                agent.logger.info(f"Skipping message from {sender_username} (already replied or own message)")
                continue
                
            agent.logger.info(f"\n💬 GENERATING REPLY to: @{sender_username} - {content[:69]}...")
            
            refer_username = random.random() < 0.7
            username_prompt = f"Refer the sender by their @{sender_username}" if refer_username else "Respond without directly referring to the sender"
            prompt = REPLY_ECHOCHAMBER_PROMPT.format(
                content=content,
                sender_username=sender_username,
                room_topic=agent.context['room_info']['topic'],
                tags=", ".join(agent.context['room_info']['tags']),
                username_prompt=username_prompt
            )
            reply = agent.prompt_llm(prompt)
            
            if reply:
                agent.logger.info(f"\n🚀 Posting reply: '{reply[:69]}...'")
                agent.connection_manager.perform_action(
                    connection_name="echochambers",
                    action_name="send-message",
                    params=[reply]
                )
                agent.context["echochambers_replied_messages"].add(message_id)
                agent.logger.info("✅ Reply posted successfully!")
                return True
    else:
        agent.logger.info("No messages in history")
    return False