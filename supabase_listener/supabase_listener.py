import os
import asyncio
from typing import Optional
import requests

from realtime import AsyncRealtimeClient, RealtimeSubscribeStates


URL = f"wss://{os.environ['SUPABASE_URL'].replace('https://', '')}/realtime/v1"
KEY = os.environ["SUPABASE_KEY"]

ACTION_ENDPOINT = os.environ["ACTION_ENDPOINT"]


async def main():
    

    socket = AsyncRealtimeClient(URL, KEY)
    channel = socket.channel("test-channel")

    def _on_subscribe(status: RealtimeSubscribeStates, err: Optional[Exception]):
        if status == RealtimeSubscribeStates.SUBSCRIBED:
            print("Connected!")
        elif status == RealtimeSubscribeStates.CHANNEL_ERROR:
            print(f"There was an error subscribing to channel: {err.args}")
        elif status == RealtimeSubscribeStates.TIMED_OUT:
            print("Realtime server did not respond in time.")
        elif status == RealtimeSubscribeStates.CLOSED:
            print("Realtime channel was unexpectedly closed.")


    def handle_new_record(payload):
        new_record = payload["data"]["record"]
        requests.post(f"{ACTION_ENDPOINT}/schedule", json=new_record)
        

    channel.on_postgres_changes("INSERT", schema="public", table="task", callback=handle_new_record)

    await channel.subscribe(_on_subscribe)

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main()) 