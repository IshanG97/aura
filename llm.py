import json
from config import config
from openai import OpenAI
import asyncio

client = OpenAI(api_key=config['OPENAI_KEY'])

async def generate_llm_response(user_id: str) -> str:
    with open("health_log.json", "r") as f:
        logs = json.load(f)
    
    # Filter messages for this user only
    user_logs = [l for l in logs if l["sender"] == user_id]
    
    # Use last 10 entries from conversation (user + assistant)
    recent_logs = user_logs[-20:]

    # Build conversation history in chat-like form
    history = "\n".join(
        f"{'You' if l['role'] == 'user' else 'Aura'}: {l['message']}"
        for l in recent_logs
    )

    # OpenAI Python SDK v1.x is currently sync — if async is required, you can wrap this with asyncio.to_thread()
    response = await asyncio.to_thread(
        client.responses.create,
        model="gpt-4o",
        instructions="You are Aura, a personalized, empathetic, WhatsApp-based wellness coach. Your mission is to guide users toward sustainable health habits through tailored micro-actions, delivered as concise, engaging WhatsApp messages. Your tone is warm, supportive, and never clinical, adapting to the user's personality archetype. You celebrate small wins, offer gentle support for setbacks, and NEVER provide medical advice. Your goal is to foster positive, achievable micro-habits that align with the user’s health goals. Also, don't add words like 'Aura:' in the beginning of your responses.",
        input=history
    )

    return response.output_text
