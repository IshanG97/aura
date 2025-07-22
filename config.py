import os

from dotenv import load_dotenv

def load_config():
    if os.path.exists(
        ".env"
    ):  # this makes it so .env files override whatever other env vars have been loaded in
        load_dotenv(".env", override=True)

    config = {
        "WHATSAPP_TOKEN": os.getenv("WHATSAPP_TOKEN"),
        "WEBHOOK_VERIFICATION_TOKEN": os.getenv("WEBHOOK_VERIFICATION_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv("PHONE_NUMBER_ID"),
<<<<<<< HEAD
=======
        "RECIPIENT_PHONE": os.getenv("RECIPIENT_PHONE"),
>>>>>>> 318d7eb76fd3c197c96accfe140585c6ac509957
        "OPENAI_KEY": os.getenv("OPENAI_KEY"),
        "ELEVENLABS_KEY": os.getenv("ELEVENLABS_KEY"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
        "ACTION_ENDPOINT": os.getenv("ACTION_ENDPOINT")
    }

    # Validate required settings
    if not config["WHATSAPP_TOKEN"]:
        raise ValueError("WHATSAPP_TOKEN is not set")

    return config

config = load_config()