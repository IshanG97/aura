import asyncio
import json

from openai import OpenAI
from supabase import Client, create_client

from app.config import config

client = OpenAI(api_key=config["OPENAI_KEY"])

# Initialize a Supabase client within the module
supabase_url = config["SUPABASE_URL"]
supabase_key = config["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# Load tools from the JSON file
with open("app/tools.json", "r") as f:
    tools = json.load(f)


def build_chat_history(logs):
    """Builds a chat history list suitable for the OpenAI API."""
    history = []
    for log in logs:
        role = "user" if log["role"] == "user" else "assistant"
        # Handle both 'content' and 'message' fields for backward compatibility
        content = log.get("message") or log.get("content", "")
        history.append({"role": role, "content": content})
    return history


async def generate_llm_response(user_id: str) -> dict:
    """
    Generates a response from the LLM, including a user-facing reply,
    an optional tool call, and the conversation topic.
    """
    try:
        # Fetch the last 20 messages for this user from Supabase
        response = (
            supabase.table("messages")
            .select("role, message")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(20)
            .execute()
        )
        recent_logs = response.data[::-1]  # Reverse to get chronological order
    except Exception as e:
        print(f"Error fetching conversation history from Supabase: {e}")
        recent_logs = []

    messages = [
        {
            "role": "system",
            "content": "You are Aura, a personalized, empathetic WhatsApp-based personal assistant. Your mission is to help users organize their lives, set reminders, track goals, and provide helpful support across various life domains. Your tone is warm, supportive, and professional. You celebrate achievements and offer gentle encouragement. Based on the user's message, provide a conversational reply. If the user wants to set a reminder or a goal, call the appropriate tool. The user-facing reply should acknowledge the action if a tool is called (e.g., 'Okay, I've set that reminder for you!'). Also, determine a one or two-word topic for the current conversation (e.g., 'Work', 'Health', 'Personal', 'Finance').",
        },
    ]
    messages.extend(build_chat_history(recent_logs))

    # Define a function for the LLM to get the topic
    topic_tool = {
        "type": "function",
        "function": {
            "name": "set_conversation_topic",
            "description": "Sets the topic of the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "A one or two-word topic for the conversation.",
                    }
                },
                "required": ["topic"],
            },
        },
    }

    all_tools = tools + [topic_tool]

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=messages,
        tools=all_tools,
        tool_choice="auto",
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    topic = "General"
    task_tool_call = None

    if tool_calls:
        for tool_call in tool_calls:
            if tool_call.function.name == "set_conversation_topic":
                try:
                    topic = json.loads(tool_call.function.arguments).get(
                        "topic", "General"
                    )
                except json.JSONDecodeError:
                    pass  # Keep default topic if arguments are invalid
            else:
                task_tool_call = tool_call  # This is the task-related tool call

    return {
        "reply": response_message.content or "Got it!",
        "tool_call": task_tool_call,
        "topic": topic,
    }
