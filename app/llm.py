import json
from app.config import config
from openai import OpenAI
import asyncio

client = OpenAI(api_key=config['OPENAI_KEY'])

tools = [
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a reminder for the user (e.g., 'Remind me to drink water every hour').",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The content of the reminder (e.g., 'Drink water')."}
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_goal",
            "description": "Create a goal for the user (e.g., 'My goal is to run a 5k').",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The content of the goal (e.g., 'Run a 5k')."}
                },
                "required": ["content"],
            },
        },
    },
]

def build_chat_history(logs):
    """Builds a chat history list suitable for the OpenAI API."""
    history = []
    for log in logs:
        role = "user" if log["role"] == "user" else "assistant"
        history.append({"role": role, "content": log["message"]})
    return history

async def generate_llm_response(user_id: str) -> dict:
    """
    Generates a response from the LLM, including a user-facing reply
    and an optional tool call.
    """
    try:
        with open("health_log.json", "r") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    user_logs = [l for l in logs if l.get("sender") == user_id]
    recent_logs = user_logs[-20:]
    
    messages = [
        {"role": "system", "content": "You are Aura, a personalized, empathetic, WhatsApp-based wellness coach. Your mission is to guide users toward sustainable health habits. Your tone is warm and supportive. You celebrate small wins and offer gentle support. NEVER provide medical advice. Based on the user's message, provide a conversational reply. If the user wants to set a reminder or a goal, call the appropriate tool. The user-facing reply should acknowledge the action if a tool is called (e.g., 'Okay, I've set that reminder for you!')."},
    ]
    messages.extend(build_chat_history(recent_logs))

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    # We can have multiple tool calls, but we'll only process the first one for now.
    first_tool_call = tool_calls[0] if tool_calls else None

    return {
        "reply": response_message.content or "Got it!",
        "tool_call": first_tool_call
    }