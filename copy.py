

import cv2
import json
import time
import fcntl
import numpy as np
import os
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# 创建日志目录和文件
os.makedirs("logs", exist_ok=True)
os.makedirs("pictures", exist_ok=True)
EVENT_LOG = "logs/events.log"


def clean_old_images():
    """定期清理1天前的图片"""
    MAX_AGE = 86400  # 1天（秒）
    now = time.time()
    for filename in os.listdir("pictures"):
        filepath = os.path.join("pictures", filename)
        if os.path.isfile(filepath) and (now - os.path.getctime(filepath)) > MAX_AGE:
            os.remove(filepath)


def is_stable_tracking(obj_id, current_bbox, track_history):
    """检查跟踪稳定性（位移突变<60像素）"""
    if obj_id not in track_history:
        return True
    last_bbox = track_history[obj_id]["bbox"]
    # 计算中心点位移
    dx = abs((current_bbox[0] + current_bbox[2]) / 2 - (last_bbox[0] + last_bbox[2]) / 2)
    dy = abs((current_bbox[1] + current_bbox[3]) / 2 - (last_bbox[1] + last_bbox[3]) / 2)
    return dx < 60 and dy < 60


# 写日志的函数（带事件合并）
pending_events = {}


def log_event(event_type, obj_id, data=None):
    global pending_events
    # 合并连续重复事件
    if obj_id in pending_events:
        last_event = pending_events[obj_id]
        if last_event["event_type"] == event_type and (time.time() - last_event["timestamp"]) < 5:
            return

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

    pending_events[obj_id] = {"event_type": event_type, "timestamp": time.time()}


# -------------------------- 主程序 --------------------------
model = YOLO("models/yolov8n.pt")
deepsort = DeepSort(max_age=60, n_init=5, nn_budget=200)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

# 参数配置
parking_threshold = 2  # 基础停留阈值（秒）
min_parking_duration = 5  # 新增：最小有效违停时间（秒）
track_history = {}  # 新增：记录轨迹稳定性
current_parking = {}
last_clean_time = time.time()

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    active_ids = set()

    # -------------------------- YOLO检测 --------------------------
    results = model(frame)
    detections = []
    for result in results:
        for box in result.boxes:
            if len(box.xyxy) == 0:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0].item())
            cls = int(box.cls[0].item())
            if conf > 0.5 and cls in [1, 3]:
                detections.append([x1, y1, x2, y2, conf])

    # -------------------------- DeepSORT跟踪 --------------------------
    if detections:
        formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
        tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)

        for obj in tracked_objects:
            try:
                bbox = obj.to_tlbr()
                obj_id = int(obj.track_id)
            except:
                continue

            # 轨迹稳定性检查
            current_bbox = list(map(int, bbox))
            if not is_stable_tracking(obj_id, current_bbox, track_history):
                continue

            # 更新轨迹历史
            track_history[obj_id] = {"bbox": current_bbox}
            active_ids.add(obj_id)

            # 计算停留时间（带稳定性补偿）
            track_history[obj_id]["frames"] = track_history.get(obj_id, {}).get("frames", 0) + 1
            stay_time = track_history[obj_id]["frames"] / 30  # 假设30FPS

            # 绘制界面
            color = (0, 255, 0)
            cv2.rectangle(frame, (current_bbox[0], current_bbox[1]),
                          (current_bbox[2], current_bbox[3]), color, 2)
            cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
                        (current_bbox[0], current_bbox[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # -------------------------- 违停检测（带延迟触发）--------------------------
            if stay_time > parking_threshold:
                # 首次触发时初始化计时器
                if obj_id not in current_parking:
                    current_parking[obj_id] = {
                        "start_time": time.time(),
                        "image_saved": False
                    }

                # 检查是否满足最小持续时间
                elapsed = time.time() - current_parking[obj_id]["start_time"]
                if elapsed >= min_parking_duration and not current_parking[obj_id]["image_saved"]:
                    # 保存截图
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                    filename = f"pictures/{timestamp}_id_{obj_id}.jpg"
                    cv2.imwrite(filename, frame)

                    # 记录日志
                    log_event("parking", obj_id, {
                        "image_path": filename,
                        "duration": elapsed
                    })
                    current_parking[obj_id]["image_saved"] = True

                # 绘制红色警告框
                cv2.rectangle(frame, (current_bbox[0], current_bbox[1]),
                              (current_bbox[2], current_bbox[3]), (0, 0, 255), 2)
                cv2.putText(frame, "Illegal Parking!",
                            (current_bbox[0], current_bbox[1] - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # -------------------------- 处理离开车辆 --------------------------
    left_ids = [obj_id for obj_id in current_parking if obj_id not in active_ids]
    for obj_id in left_ids:
        if current_parking[obj_id]["image_saved"]:
            log_event("left", obj_id, {
                "duration": time.time() - current_parking[obj_id]["start_time"]
            })
        del current_parking[obj_id]
        del track_history[obj_id]

    # -------------------------- 每小时清理图片 --------------------------
    if time.time() - last_clean_time > 3600:
        clean_old_images()
        last_clean_time = time.time()

    # 显示画面
    cv2.imshow("Non-Motor Vehicle Tracker", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()