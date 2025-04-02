# utils/logger.py
# 日志管理（写入、合并）
import json
import time
import fcntl
import os
from config import LOG_DIR

EVENT_LOG = os.path.join(LOG_DIR, "events.log")

def log_event(event_type, obj_id, data=None):
    """写入日志"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    event = {
        "timestamp": timestamp,
        "event_type": event_type,
        "obj_id": obj_id,
        "data": data or {}
    }

    with open(EVENT_LOG, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(event) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
