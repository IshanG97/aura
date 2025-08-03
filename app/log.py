from supabase import create_client, Client
from app.config import config

# Initialize a Supabase client within the module
supabase_url = config["SUPABASE_URL"]
supabase_key = config["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

def append_health_log(log_entry: dict):
    """Appends a message log to the Supabase 'messages' table."""
    try:
        # Ensure the entry has the required fields
        required_fields = ["user_id", "role", "message"]
        if not all(field in log_entry for field in required_fields):
            print(f"Error: Log entry is missing required fields. Entry: {log_entry}")
            return

        supabase.table("messages").insert(log_entry).execute()

    except Exception as e:
        print(f"Error appending health log to Supabase: {e}")