import os
import json
from datetime import datetime


class EventLogger:
    def __init__(self):
        os.makedirs("logs/metadata", exist_ok=True)
        self.file = "logs/metadata/events.jsonl"

    def log(self, event_type, image_path, data):
        entry = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            "event": event_type,
            "image": image_path,
            "data": data
        }

        with open(self.file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")