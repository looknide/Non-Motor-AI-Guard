import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), "../logs")))  # 项目根目录
if not os.path.exists(BASE_DIR):  # 如果目录不存在，创建它
    os.makedirs(BASE_DIR)
EVENT_LOG = os.path.join(BASE_DIR, "events.log")
# 创建日志目录
os.makedirs(BASE_DIR, exist_ok=True)

def log_event(event_type, obj_id, data=None):
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "obj_id": obj_id,
        "data": data
    }

    event_json = json.dumps(event, ensure_ascii=False)
    print(f"Logging event: {event_json}")

    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write(event_json + "\n")
