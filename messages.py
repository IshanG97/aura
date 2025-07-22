from config import config
import requests

# endpoint to send a custom message when triggered
def send_message(to_number: str, message: str):
    url = f"https://graph.facebook.com/v22.0/{config['PHONE_NUMBER_ID']}/messages"

    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message,
        },
    }

    response = requests.post(url, headers=headers, json=payload)

    print("📤 Status:", response.status_code)
    try:
        print("📤 Response:", response.json())
    except Exception as e:
        print("⚠️ Could not decode JSON:", e, "| Raw:", response.text)
    
    return response

def extract_message_data(payload: dict) -> dict:
    try:
        value = payload["entry"][0]["changes"][0]["value"]

        message = value.get("messages", [{}])[0]
        contact = value.get("contacts", [{}])[0]

        return {
            "sender_wa_id": message.get("from"),  # WhatsApp number
            "sender_name": contact.get("profile", {}).get("name"),
            "message_id": message.get("id"),
            "timestamp": message.get("timestamp"),
            "type": message.get("type"),
            "text": message.get("text", {}).get("body"),  # Only for text messages
            "raw": message  # Optional: include full raw message object
        }
    except Exception as e:
        print("⚠️ Error extracting message:", e)
        return {}