import tempfile

import requests
from elevenlabs.client import ElevenLabs

from app.config import config

elevenlabs_stt = ElevenLabs(api_key=config["ELEVENLABS_KEY"])


def download_whatsapp_audio(media_id: str) -> str:
    """
    Download WhatsApp voice message by media ID and save it to a temp file.
    Returns path to the downloaded file.
    """
    # Step 1: Get the media download URL
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {config['WHATSAPP_TOKEN']}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    download_url = response.json().get("url")

    # Step 2: Download the media bytes
    audio_response = requests.get(download_url, headers=headers, stream=True)
    audio_response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
        for chunk in audio_response.iter_content(chunk_size=8192):
            tmp.write(chunk)
        return tmp.name


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file using ElevenLabs Speech-to-Text.
    """
    with open(file_path, "rb") as audio_file:
        result = elevenlabs_stt.speech_to_text.convert(
            file=audio_file,
            model_id="scribe_v1",  # Required
            language_code="eng",  # Optional: change or set to None for auto-detect
            tag_audio_events=False,  # Optional
            diarize=False,  # Optional
        )

    return result.text
