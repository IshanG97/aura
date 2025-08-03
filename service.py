from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime, UTC
from app.config import config
from app.llm import generate_llm_response, get_intent
from app.log import append_health_log
from app.messages import send_text_message, extract_message_data, send_audio_message
import httpx
from app.tts import generate_voice_with_elevenlabs, upload_audio_to_whatsapp
from app.stt import download_whatsapp_audio, transcribe_audio
import asyncio
from typing import Optional
from realtime import AsyncRealtimeClient, RealtimeSubscribeStates
from supabase import create_client, Client
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Initialize Supabase client
supabase_url = config["SUPABASE_URL"]
supabase_key = config["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

app = FastAPI()

# --- Scheduling Logic from action_server.py ---

async def reminder_job(task_id, description):
    send_text_message("447397235771", description)

def parse_frequency(freq):
    freq = float(freq)
    if freq < 1:
        hours = int(freq * 24)
        return {"hours": hours}
    return {"days": int(freq)}

def schedule_task(task):
    task_id = task["id"]
    created_at = task["created_at"]
    frequency = task["freq"]
    content = task["content"]
    start_time = datetime.fromisoformat(created_at)

    scheduler.add_job(
        reminder_job,
        trigger=IntervalTrigger(start_date=start_time, **parse_frequency(frequency)),
        args=[task_id, content],
        id=f"task-{task_id}",
        replace_existing=True
    )
    print(f"Scheduled task #{task_id} at {start_time}")

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

    channel.on_postgres_changes("INSERT", schema="public", table="task", callback=on_new_task)
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

    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "sender": message_data["sender_wa_id"],
        "name": message_data["sender_name"],
        "message": user_text,
        "role": "user"
    }
    append_health_log(log_entry)
    print("📥 Received message:", log_entry)

    print("🧠 Generating LLM response for user:", log_entry["sender"])
    reply, history = await generate_llm_response(log_entry["sender"])

    intent = get_intent(history)
    if intent.get("type"):
        task_type = intent["type"]
        task_content = intent["content"]
        
        # Directly create the task in the database
        print(f"Creating task of type '{task_type}' with content: {task_content}")
        user = supabase.table("user").select("*").eq("phone", message_data["sender_wa_id"]).execute().data[0]
        
        new_task_data = {
            "user_id": user["id"],
            "info_id": 1, # Placeholder
            "type": "Reminder" if task_type == "reminder" else "Goal",
            "active": True,
            "freq": 2 if user.get("personality") == "anxious" else 0.5,
            "content": task_content
        }
        
        res = supabase.table("task").insert(new_task_data).execute()
        print("Task creation response:", res.data)


    assistant_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "sender": message_data["sender_wa_id"],
        "name": "Aura",
        "message": reply,
        "role": "assistant"
    }
    append_health_log(assistant_entry)
    print("🧠 LLM response generated:", assistant_entry)

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
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    expected = config["WEBHOOK_VERIFICATION_TOKEN"]
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return JSONResponse(status_code=403, content={"error": "Verification failed"})

# --- User and Task CRUD endpoints from action_server.py ---

@app.post("/users")
def create_user(request: Request):
    data = request.json()
    res = supabase.table("user").insert({"phone": data["phone"], "name": data["name"]}).execute()
    return JSONResponse(content=res.data, status_code=201)

@app.get("/users/{user_id}")
def get_user(user_id: int):
    res = supabase.table("user").select("*").eq("id", user_id).execute().data
    return JSONResponse(content=res, status_code=200)

@app.put("/users/{user_id}")
def update_user(user_id: int, request: Request):
    data = request.json()
    res = supabase.table("user").update(data).eq("id", user_id).execute().data
    return JSONResponse(content=res, status_code=200)

@app.get("/tasks/{user_id}")
def get_tasks(user_id: int):
    res = supabase.table("task").select("*").eq("user_id", user_id).eq("active", True).execute().data
    return JSONResponse(content=res, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)