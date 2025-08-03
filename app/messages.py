import requests

from app.config import config


# endpoint to send a custom message when triggered
def send_text_message(to_number: str, message: str):
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

        message_type = message.get("type")

        return {
            "sender_wa_id": message.get("from"),
            "sender_name": contact.get("profile", {}).get("name"),
            "message_id": message.get("id"),
            "timestamp": message.get("timestamp"),
            "type": message_type,
            "text": message.get("text", {}).get("body")
            if message_type == "text"
            else None,
            "audio_id": message.get("audio", {}).get("id")
            if message_type == "audio"
            else None,
            "raw": message,
        }
    except Exception as e:
        print("⚠️ Error extracting message:", e)
        return {}


def send_audio_message(to_number: str, media_id: str):
    url = f"https://graph.facebook.com/v18.0/{config['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "audio",
        "audio": {"id": media_id},
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response
