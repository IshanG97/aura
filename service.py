import requests
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from config import config

app = FastAPI()

# health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "all systems operational"}

# endpoint to send a custom message when triggered
@app.post("/swole-message")
async def send_message():
    url = f"https://graph.facebook.com/v22.0/{config['PHONE_NUMBER_ID']}/messages"

    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": config["RECIPIENT_PHONE"],
        "type": "text",
        "text": {
            "body": "Hi big boy, time to get swole 💪",
        },
    }

    response = requests.post(url, headers=headers, json=payload)
    return JSONResponse(status_code=response.status_code, content=response.json())

# webhook to receive incoming messages
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    body = await request.json()
    print("📥 Incoming webhook data:", body)

    try:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        text = message["text"]["body"]
        print(f"📨 Message from {sender}: {text}")
    except Exception as e:
        print("⚠️ Could not extract message:", e)

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
    uvicorn.run(app, host="0.0.0.0", port=8080)
