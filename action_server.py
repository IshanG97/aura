import os
from flask import Flask, request, Response, jsonify, abort
from supabase import create_client, Client
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from messages import send_text_message
from config import config

scheduler = BackgroundScheduler()
scheduler.start()

url = config["SUPABASE_URL"]
key = config["SUPABASE_KEY"]

supabase = create_client(url, key)



async def reminder_job(task_id, description):
    send_text_message("447397235771", description)


def parse_frequency(freq):
    freq = float(freq)
    # freq in days, e.g 1 => every day

    if freq < 1:
        hours = int(freq * 24)

        return {"hours": hours}
    
    return {"days": int(freq)}


app = Flask(__name__)

@app.route("/")
def index():
    return "Alive"


@app.route("/users", methods=["POST"])
def users():
    phone = request.json["phone"]
    name = request.json["name"]

    try:
        res = supabase.table("user").insert(
            {
                "phone": phone,
                "name": name
            }
        ).execute()
        return res.data
    
    except:
        return jsonify({'error': 'Something went wrong'}), 500


@app.route("/users/<int:user_id>", methods=["GET", "PUT", "DELETE"])
def user(user_id):
    if request.method == "GET":
        res = supabase.table("user").select("*").eq("id",user_id).execute().data
        
        return jsonify(res), 200

    elif request.method == "PUT":
        res = supabase.table("user").update(request.json).eq("id", user_id).execute().data

        return jsonify(res), 200

    elif request.method == "DELETE":
        pass


@app.route("/tasks/<int:user_id>", methods=["GET", "PUT", "POST"])
def tasks(user_id):

    data = request.get_json()

    if request.method == "GET":
        res = supabase.table("task").select("*").eq("user_id", user_id).eq("active", True).execute().data
        return jsonify(res), 200
    
    elif request.method == "POST":

        user = supabase.table("user").select("*").eq("id", user_id).execute().data[0]

        res = supabase.table("task").insert({
            "user_id": user_id,
            "info_id": data["info_id"],
            "type": data["type"],
            "active": True,
            "freq": 2 if user["personality"] == "anxious" else .5, # every 2 days if user is anxious else every 1/2 day (12 hours)
            "content": data["content"]
        }).execute()

        return res.data


@app.route("/schedule", methods=["POST"])
def schedule_task():
    data = request.get_json()

    task_id = data["id"]
    created_at = data["created_at"]
    frequency = data["freq"]
    content = data["content"]

    start_time = datetime.fromisoformat(created_at)


    scheduler.add_job(
        reminder_job,
        trigger=IntervalTrigger(start_date=start_time, **parse_frequency(frequency)),
        args=[task_id, content],
        id=f"task-{task_id}",
        replace_existing=True
    )

    print(f"Scheduled one-time task #{task_id} at {start_time}")

    return {"status": "scheduled"}, 200


if __name__ == "__main__":
    app.run(port=5000)