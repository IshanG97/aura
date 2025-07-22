import tempfile
import requests
from config import config
from elevenlabs.client import ElevenLabs
import tempfile
import os

# Set up ElevenLabs client
elevenlabs = ElevenLabs(
    api_key=config["ELEVENLABS_KEY"]
)

def generate_voice_with_elevenlabs(text: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb") -> str:
    """
    Generate full audio from text using ElevenLabs SDK (streaming),
    save it to a temp MP3 file, and return the file path.
    """
    stream = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        for chunk in stream:
            tmp.write(chunk)
        return tmp.name

def upload_audio_to_whatsapp(file_path: str) -> str:
    """
    Upload an MP3 audio file to WhatsApp via the Meta Graph API and return the media ID.
    """
    url = f"https://graph.facebook.com/v22.0/{config['PHONE_NUMBER_ID']}/media"
    headers = {
        "Authorization": f"Bearer {config['WHATSAPP_TOKEN']}"
    }
    files = {
        "file": (os.path.basename(file_path), open(file_path, "rb"), "audio/mpeg"),
    }
    data = {
        "messaging_product": "whatsapp",  # ✅ must be included!
        "type": "audio/mpeg"
    }

    response = requests.post(url, headers=headers, files=files, data=data)

    try:
        response.raise_for_status()
        print("✅ Media upload response:", response.status_code, response.json())

    except requests.exceptions.HTTPError:
        print("❌ WhatsApp upload failed:", response.status_code, response.text)
        raise

    media_id = response.json().get("id")
    if not media_id:
        raise RuntimeError("No media ID returned by WhatsApp.")

    return media_id

