import os
import time
import websocket
import json
import threading
import requests

from config import config

url = config["SUPABASE_URL"]
key = config["SUPABASE_KEY"]

TABLE = "task"
SCHEMA = "public"
BACKEND_URL = config["ACTION_ENDPOINT"]  # Flask endpoint


def send_heartbeat(ws):
    while True:
        time.sleep(30)
        heartbeat_msg = {
            "topic": "phoenix",
            "event": "heartbeat",
            "payload": {},
            "ref": "heartbeat_ref"
        }
        ws.send(json.dumps(heartbeat_msg))

def on_message(ws, message):
    print(message)
    msg = json.loads(message)

    # Confirm it's a new INSERT message
    if msg.get("event") == "INSERT":
        new_row = msg.get("payload", {}).get("record", {})
        if new_row.get("type") == "Reminder":
            print("New Reminder:", new_row)

            # Send to Flask for scheduling
            requests.post(BACKEND_URL, json=new_row)

def on_open(ws):
    print("Connected to Supabase Realtime")

    # Subscribe to INSERTS on Task table
    join_msg = {
        "topic": f"realtime:{SCHEMA}:{TABLE}",
        "event": "phx_join",
        "payload": {},
        "ref": "1"
    }

    listen_msg = {
        "topic": f"realtime:{SCHEMA}:{TABLE}",
        "event": "postgres_changes",
        "payload": {
            "events": ["INSERT"],
            "schema": SCHEMA,
            "table": TABLE,
        },
        "ref": "2"
    }

    ws.send(json.dumps(join_msg))
    ws.send(json.dumps(listen_msg))

    threading.Thread(target=send_heartbeat, args=(ws,), daemon=True).start()


def on_error(ws, error):
    print(f"Error: {error}")

def start_listener():
    realtime_url = f"wss://{url}/realtime/v1"
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }

    ws = websocket.WebSocketApp(
        realtime_url,
        header=[f"{k}: {v}" for k, v in headers.items()],
        on_message=on_message,
        on_open=on_open,
        on_error=on_error
    )

    ws.run_forever()


if __name__ == "__main__":
    start_listener()

# Start it in a background thread
# threading.Thread(target=start_listener, daemon=True).start()
