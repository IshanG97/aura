import asyncio
import json
from datetime import datetime
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from realtime import AsyncRealtimeClient, RealtimeSubscribeStates
from supabase import Client, create_client

from app.config import config
from app.llm import generate_llm_response
from app.log import append_message_log
from app.messages import extract_message_data, send_audio_message, send_text_message
from app.stt import download_whatsapp_audio, transcribe_audio
from app.tts import generate_voice_with_elevenlabs, upload_audio_to_whatsapp

# Initialize Supabase client
supabase_url = config["SUPABASE_URL"]
supabase_key = config["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

app = FastAPI()

# --- Scheduling Logic from action_server.py ---


async def reminder_job(user_id, description):
    try:
        user = supabase.table("users").select("phone").eq("id", user_id).execute().data
        if user:
            phone_number = user[0]["phone"]
            send_text_message(phone_number, description)
            print(f"Sent reminder to {phone_number} for task.")
        else:
            print(f"Error: Could not find user with ID {user_id} to send reminder.")
    except Exception as e:
        print(f"Error sending reminder for user {user_id}: {e}")


def parse_frequency(freq):
    freq = float(freq)
    if freq < 1:
        hours = int(freq * 24)
        return {"hours": hours}
    return {"days": int(freq)}


def schedule_task(task):
    task_id = task["id"]
    user_id = task["user_id"]  # Get user_id from the task
    created_at = task["created_at"]
    frequency = task["freq"]
    content = task["content"]
    start_time = datetime.fromisoformat(created_at)

    scheduler.add_job(
        reminder_job,
        trigger=IntervalTrigger(start_date=start_time, **parse_frequency(frequency)),
        args=[user_id, content],  # Pass user_id to the job
        id=f"task-{task_id}",
        replace_existing=True,
    )
    print(f"Scheduled task #{task_id} for user #{user_id} at {start_time}")


# --- Supabase Listener Logic ---


async def run_supabase_listener():
    ws_url = f"wss://{supabase_url.replace('https://', '')}/realtime/v1"
    socket = AsyncRealtimeClient(ws_url, supabase_key)
    channel = socket.channel("test-channel")

    def on_subscribe(status: RealtimeSubscribeStates, err: Optional[Exception]):
        if status == RealtimeSubscribeStates.SUBSCRIBED:
            print("Successfully subscribed to Supabase Realtime!")
        else:
            print(f"Error subscribing to Supabase Realtime: {err}")

    def on_new_task(payload):
        new_record = payload["data"]["record"]
        print(f"New task received from Supabase: {new_record['id']}")
        schedule_task(new_record)

    channel.on_postgres_changes(
        "INSERT", schema="public", table="task", callback=on_new_task
    )
    await channel.subscribe(on_subscribe)

    while True:
        await asyncio.sleep(1)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_supabase_listener())


# --- FastAPI Endpoints ---


@app.get("/health")
async def health_check():
    return {"status": "all systems operational"}


@app.post("/send-onboarding-message")
async def send_onboarding_message(to_number: str):
    # ... (existing code remains the same)
    url = f"https://graph.facebook.com/v22.0/{config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {"name": "aura_welcome", "language": {"code": "en"}},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    print("📤 Onboarding status:", response.status_code)
    return JSONResponse(status_code=response.status_code, content=response.json())


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    body = await request.json()
    print("📦 Incoming webhook payload:", body)
    message_data = extract_message_data(body)

    if not message_data:
        return {"status": "ignored (no message data)"}

    if message_data.get("audio_id"):
        audio_path = download_whatsapp_audio(message_data["audio_id"])
        user_text = transcribe_audio(audio_path)
    elif message_data.get("text"):
        user_text = message_data["text"]
    else:
        return {"status": "ignored (no valid input)"}

    # --- Log User Message to Supabase ---
    try:
        user_res = (
            supabase.table("users")
            .select("id")
            .eq("phone", message_data["sender_wa_id"])
            .execute()
        )
        if not user_res.data:
            # This is a new user, create them first
            new_user_res = (
                supabase.table("users")
                .insert(
                    {
                        "phone": message_data["sender_wa_id"],
                        "name": message_data["sender_name"],
                    }
                )
                .execute()
            )
            user_id = new_user_res.data[0]["id"]
        else:
            user_id = user_res.data[0]["id"]

        # Step 1: Log user message to temporary conversation first
        # Use existing open conversation or create a temporary one
        temp_conversation_res = (
            supabase.table("conversations")
            .select("id, topic")
            .eq("user_id", user_id)
            .eq("status", "open")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )

        # Use existing or create temp conversation
        if temp_conversation_res.data:
            temp_conversation_id = temp_conversation_res.data[0]["id"]
        else:
            # Create temporary conversation
            temp_conversation = (
                supabase.table("conversations")
                .insert(
                    {
                        "user_id": user_id,
                        "topic": "General",
                        "status": "open",
                    }
                )
                .execute()
            )
            temp_conversation_id = temp_conversation.data[0]["id"]

        # Log user message to get it in history
        temp_log_entry = {
            "user_id": user_id,
            "conversation_id": temp_conversation_id,
            "role": "user",
            "content": user_text,
            "message_type": "audio" if message_data.get("audio_id") else "text",
            "audio_id": message_data.get("audio_id"),
            "message_id": message_data.get("message_id"),
        }
        append_message_log(temp_log_entry)
        print("📥 Temp logged user message")

    except Exception as e:
        print(f"Error handling user message logging: {e}")
        return {"status": "error logging message"}

    # Step 2: Generate LLM response with current message in history
    print("🧠 Generating LLM response for user:", user_id)
    llm_response = await generate_llm_response(user_id)
    current_topic = llm_response.get("topic", "General")

    # Step 3: Determine final conversation based on topic
    try:
        final_conversation_id = None
        topic_switched = False

        # Get all open conversations to check topics
        all_conversations_res = (
            supabase.table("conversations")
            .select("id, topic")
            .eq("user_id", user_id)
            .eq("status", "open")
            .execute()
        )

        # Look for existing conversation with same topic
        for conv in all_conversations_res.data:
            if conv.get("topic") == current_topic:
                final_conversation_id = conv["id"]
                print(
                    f"📝 Found existing conversation #{final_conversation_id} for topic: {current_topic}"
                )
                break

        # If no conversation exists for this topic, create one
        if not final_conversation_id:
            # Check if we're switching from a different topic
            if (
                temp_conversation_res.data
                and temp_conversation_res.data[0].get("topic") != current_topic
            ):
                topic_switched = True
                old_topic = temp_conversation_res.data[0].get("topic")
                print(f"🔄 Topic switched from '{old_topic}' to '{current_topic}'")

            new_conversation = (
                supabase.table("conversations")
                .insert(
                    {
                        "user_id": user_id,
                        "topic": current_topic,
                        "status": "open",
                    }
                )
                .execute()
            )
            final_conversation_id = new_conversation.data[0]["id"]
            print(
                f"📝 Created new conversation #{final_conversation_id} for topic: {current_topic}"
            )

        # Step 4: Move message to correct conversation if needed
        if final_conversation_id != temp_conversation_id:
            supabase.table("messages").update(
                {"conversation_id": final_conversation_id}
            ).eq("id", temp_log_entry.get("id") or temp_conversation_id).execute()
            print(f"📝 Moved message to correct conversation #{final_conversation_id}")

        # Step 5: Update topic of conversation if it was temporary
        if (
            temp_conversation_res.data
            and temp_conversation_res.data[0].get("topic") == "General"
            and current_topic != "General"
        ):
            supabase.table("conversations").update({"topic": current_topic}).eq(
                "id", final_conversation_id
            ).execute()
            print(f"📝 Updated conversation topic to: {current_topic}")

        conversation_id = final_conversation_id

    except Exception as e:
        print(f"Error managing conversations: {e}")
        conversation_id = temp_conversation_id
        topic_switched = False

    reply = llm_response["reply"]
    tool_call = llm_response["tool_call"]

    # Add debug message for topic switching
    if topic_switched:
        debug_message = f"🔄 Switching to {current_topic} topic"
        send_text_message(message_data["sender_wa_id"], debug_message)

    # --- Background Action Execution ---
    if tool_call:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        content = arguments.get("content")

        if content and (
            function_name == "create_reminder" or function_name == "create_goal"
        ):
            print(f"Executing tool: {function_name} with content: {content}")

            try:
                user_res = (
                    supabase.table("users").select("*").eq("id", user_id).execute()
                )
                if not user_res.data:
                    raise Exception(f"User not found with id {user_id}")
                user = user_res.data[0]

                task_type = "Reminder" if function_name == "create_reminder" else "Goal"

                new_task_data = {
                    "user_id": user["id"],
                    "conversation_id": conversation_id,
                    "type": task_type,
                    "active": True,
                    "freq": 2 if user.get("personality") == "anxious" else 0.5,
                    "content": content,
                }

                res = supabase.table("tasks").insert(new_task_data).execute()
                print("Task creation response:", res.data)

            except Exception as e:
                print(f"Error executing tool {function_name}: {e}")

    # --- Log Assistant Response ---
    assistant_log_entry = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "role": "assistant",
        "message": reply,
        "message_type": "text",
    }
    append_message_log(assistant_log_entry)
    print("🧠 Logged assistant response:", assistant_log_entry)

    # --- Send Reply to User ---
    if message_data.get("text"):
        send_text_message(message_data["sender_wa_id"], reply)
    if message_data.get("audio_id"):
        voice_path = generate_voice_with_elevenlabs(reply)
        media_id = upload_audio_to_whatsapp(voice_path)
        send_audio_message(message_data["sender_wa_id"], media_id)

    print("📤 Reply sent to user:", message_data["sender_wa_id"])
    return {"status": "received"}


@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    expected = config["WEBHOOK_VERIFICATION_TOKEN"]
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return JSONResponse(status_code=403, content={"error": "Verification failed"})


# --- User and Task CRUD endpoints from action_server.py ---


@app.post("/users")
def create_user(request: Request):
    data = request.json()
    res = (
        supabase.table("users")
        .insert({"phone": data["phone"], "name": data["name"]})
        .execute()
    )
    return JSONResponse(content=res.data, status_code=201)


@app.get("/users/{user_id}")
def get_user(user_id: int):
    res = supabase.table("users").select("*").eq("id", user_id).execute().data
    return JSONResponse(content=res, status_code=200)


@app.put("/users/{user_id}")
def update_user(user_id: int, request: Request):
    data = request.json()
    res = supabase.table("users").update(data).eq("id", user_id).execute().data
    return JSONResponse(content=res, status_code=200)


@app.get("/tasks/{user_id}")
def get_tasks(user_id: int):
    res = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("active", True)
        .execute()
        .data
    )
    return JSONResponse(content=res, status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
