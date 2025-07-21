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
        "RECIPIENT_PHONE": os.getenv("RECIPIENT_PHONE"),
        "OPENAI_KEY": os.getenv("OPENAI_KEY"),
        "ELEVEN_LABS_KEY": os.getenv("ELEVEN_LABS_KEY"),
    }

    # Validate required settings
    if not config["WHATSAPP_TOKEN"]:
        raise ValueError("WHATSAPP_TOKEN is not set")

    return config

config = load_config()