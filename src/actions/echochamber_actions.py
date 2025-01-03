import time,random
from src.action_handler import register_action

@register_action("post-echochambers")
def post_echochambers(agent, **kwargs):
    current_time = time.time()
    
    # Get room info
    room_info = agent.connection_manager.perform_action(
        connection_name="echochambers",
        action_name="get-room-info",
        params={}
    )

    # Initialize state
    if "echochambers_last_message" not in agent.state:
        agent.state["echochambers_last_message"] = 0
    if "echochambers_replied_messages" not in agent.state:
        agent.state["echochambers_replied_messages"] = set()
    
    if current_time - agent.state["echochambers_last_message"] > agent.echochambers_message_interval:
        agent.logger.info("\n📝 GENERATING NEW ECHOCHAMBERS MESSAGE")
        
        # Generate message based on room topic and tags
        previous_messages = agent.connection_manager.connections["echochambers"].sent_messages
        previous_content = "\n".join([f"- {msg['content']}" for msg in previous_messages])
        agent.logger.info(f"Found {len(previous_messages)} messages in post history")
        
        prompt = (f"Context:\n- Room Topic: {room_info['topic']}\n- Tags: {', '.join(room_info['tags'])}\n- Previous Messages:\n{previous_content}\n\nTask:\nCreate a concise, engaging message that:\n1. Aligns with the room's topic and tags\n2. Builds upon Previous Messages without repeating them, or repeating greetings, introductions, or sentences.\n3. Offers fresh insights or perspectives\n4. Maintains a natural, conversational tone\n5. Keeps length between 2-4 sentences\n\nGuidelines:\n- Be specific and relevant\n- Add value to the ongoing discussion\n- Avoid generic statements\n- Use a friendly but professional tone\n- Include a question or discussion point when appropriate\n\nThe message should feel organic and contribute meaningfully to the conversation.")
        message = agent.prompt_llm(prompt)
        
        if message:
            agent.logger.info(f"\n🚀 Posting message: '{message[:69]}...'")
            agent.connection_manager.perform_action(
                connection_name="echochambers",
                action_name="send-message",
                params=[message]  # Pass as list of values
            )
            agent.state["echochambers_last_message"] = current_time
            agent.logger.info("✅ Message posted successfully!")
            return True
    return False

@register_action("reply-echochambers")
def reply_echochambers(agent, **kwargs):
    agent.logger.info("\n🔍 CHECKING FOR MESSAGES TO REPLY TO")
    
    # Initialize replied messages set if not exists
    if "echochambers_replied_messages" not in agent.state:
        agent.state["echochambers_replied_messages"] = set()
        
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
                message_id in agent.state.get("echochambers_replied_messages", set())):
                agent.logger.info(f"Skipping message from {sender_username} (already replied or own message)")
                continue
                
            agent.logger.info(f"\n💬 GENERATING REPLY to: @{sender_username} - {content[:69]}...")
            
            refer_username = random.random() < 0.7
            username_prompt = f"Refer the sender by their @{sender_username}" if refer_username else "Respond without directly referring to the sender"
            prompt = (f"Context:\n- Current Message: \"{content}\"\n- Sender Username: @{sender_username}\n- Room Topic: {room_info['topic']}\n- Tags: {', '.join(room_info['tags'])}\n\nTask:\nCraft a reply that:\n1. Addresses the message\n2. Aligns with topic/tags\n3. Engages participants\n4. Adds value\n\nGuidelines:\n- Reference message points\n- Offer new perspectives\n- Be friendly and respectful\n- Keep it 2-3 sentences\n- {username_prompt}\n\nEnhance conversation and encourage engagement\n\nThe reply should feel organic and contribute meaningfully to the conversation.")
            reply = agent.prompt_llm(prompt)
            
            if reply:
                agent.logger.info(f"\n🚀 Posting reply: '{reply[:69]}...'")
                agent.connection_manager.perform_action(
                    connection_name="echochambers",
                    action_name="send-message",
                    params=[reply]
                )
                agent.state["echochambers_replied_messages"].add(message_id)
                agent.logger.info("✅ Reply posted successfully!")
                return True
    else:
        agent.logger.info("No messages in history")
    return False