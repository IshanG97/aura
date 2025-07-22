from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from datetime import datetime, UTC
from config import config
from llm import generate_llm_response
from log import append_health_log
from messages import send_text_message, extract_message_data, send_audio_message
import httpx
from tts import generate_voice_with_elevenlabs, upload_audio_to_whatsapp
from stt import download_whatsapp_audio, transcribe_audio

app = FastAPI()

# health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "all systems operational"}

# endpoint to send a custom message when triggered
@app.post("/send-onboarding-message")
async def send_onboarding_message(to_number: str):
    url = f"https://graph.facebook.com/v22.0/{config['PHONE_NUMBER_ID']}/messages"

    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "aura_welcome",
            "language": {
                "code": "en"
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    print("📤 Onboarding status:", response.status_code)
    try:
        print("📤 Onboarding response:", response.json())
    except Exception as e:
        print("⚠️ Could not decode onboarding JSON:", e, "| Raw:", response.text)

    return JSONResponse(status_code=response.status_code, content=response.json())


# Meta webhook posting
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    body = await request.json()
    print("📦 Incoming webhook payload:", body)

    message_data = extract_message_data(body)

    if message_data:
        if message_data.get("audio_id"):
            # Download and transcribe audio
            audio_path = download_whatsapp_audio(message_data["audio_id"])
            user_text = transcribe_audio(audio_path)
        elif message_data.get("text"):
            user_text = message_data["text"]
        else:
            return {"status": "ignored (no valid input)"}
        # save the user incoming message intno history
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sender": message_data["sender_wa_id"],
            "name": message_data["sender_name"],
            "message": user_text,
            "role": "user"
        }
        append_health_log(log_entry)
        print("📥 Received message:", log_entry)
        
        # await LLM response
        print("🧠 Generating LLM response for user:", log_entry["sender"])
        reply = await generate_llm_response(log_entry["sender"])

        # save the llm response into history
        assistant_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sender": message_data["sender_wa_id"],
            "name": "Aura",
            "message": reply,
            "role": "assistant"  # ✅ NEW
        }
        append_health_log(assistant_entry)
        print("🧠 LLM response generated:", assistant_entry)

        # send reply
<<<<<<< HEAD
        if message_data.get("text"):
            send_text_message(message_data["sender_wa_id"], reply)

        # Generate + send voice message
        if message_data.get("audio_id"):
            voice_path = generate_voice_with_elevenlabs(reply)
            media_id = upload_audio_to_whatsapp(voice_path)
            send_audio_message(message_data["sender_wa_id"], media_id)

        print("📤 Reply sent to user:", message_data["sender_wa_id"])
=======
        send_text_message(message_data["sender_wa_id"], reply)
        print("📤 Reply sent to user:", message_data["sender_wa_id"])

        # Generate + send voice message
        voice_path = generate_voice_with_elevenlabs(reply)
        media_id = upload_audio_to_whatsapp(voice_path)
        send_audio_message(message_data["sender_wa_id"], media_id)
>>>>>>> 318d7eb76fd3c197c96accfe140585c6ac509957

    return {"status": "received"}

# Meta webhook verification
@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    expected = config["WEBHOOK_VERIFICATION_TOKEN"]
    print(f"📡 Received token: '{hub_verify_token}' | Expected: '{expected}'")

    if hub_mode == "subscribe" and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge, status_code=200)

    return JSONResponse(status_code=403, content={"error": "Verification failed"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
