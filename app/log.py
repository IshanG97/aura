import json
from pathlib import Path

log_path = Path("../data/health_log.json")

def append_health_log(entry: dict):
    if log_path.exists():
        with open(log_path, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(entry)

    with open(log_path, "w") as f:
        json.dump(data, f, indent=2)