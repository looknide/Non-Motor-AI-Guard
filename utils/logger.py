# utils/logger.py
# 日志管理（写入、合并）
import json
import time
import fcntl
import os
from config import LOG_DIR
from datetime import datetime

EVENT_LOG = os.path.join(LOG_DIR, "events.log")

def log_event(event_type, obj_id, data=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_file_path = os.path.join("logs", "events.log")
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "obj_id": obj_id,
        "data": data
    }

    event_json = json.dumps(event, ensure_ascii=False)
    print(f"Logging event: {event_json}")

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(event_json + "\n")

