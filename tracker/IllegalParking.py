import cv2
import json
import time
import fcntl
import os
import numpy as np
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# 创建日志和图片目录
os.makedirs("logs", exist_ok=True)
os.makedirs("pictures", exist_ok=True)
EVENT_LOG = "logs/events.log"
if time.strftime("%H:%M") == "00:00" and os.path.exists(EVENT_LOG): # 每天 00:00，日志文件会被 重命名归档，避免长期积累导致文件过大。
    os.rename(EVENT_LOG, f"logs/events_{time.strftime('%Y%m%d')}.log")


def log_event(event_type, obj_id, data=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(EVENT_LOG, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            event = {
                "timestamp": timestamp,
                "event_type": event_type,
                "obj_id": obj_id,
                "data": data
            }
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# 加载 YOLO 模型
model = YOLO("models/yolov8n.pt")
deepsort = DeepSort(max_age=80, n_init=3, nn_budget=200)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

parking_threshold = 2  # 违停阈值（秒）
tolerance = 3.0  # 目标丢失容忍时间（秒）

frame_count = {}  # 记录累计帧数
last_bbox = {}  # 记录上一次有效的 bbox，避免突发丢失
last_seen = {}  # 记录目标最后出现时间
current_parking = {}  # 当前违停目标
id_map = {}  # 记录可能的ID变更（旧ID -> 新ID）
# ------------------------------------------------ 处理每一帧  ------------------------------------------------
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    current_time = time.time()
    active_ids = set() # 当前帧中检测到的 ID

    # YOLO 目标检测
    results = model(frame)
    detections = []
    for result in results:
        for box in result.boxes:
            if len(box.xyxy) == 0:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0].item())
            cls = int(box.cls[0].item())
            cls_name = model.names[cls]
            print(f"检测到: {cls_name} (置信度={conf:.2f})")
            # -----------------------------------追踪置信度 超过 50% 的目标----------------------------------
            if conf > 0.5 and cls in [1, 3]:  # 调整类别
                detections.append([x1, y1, x2, y2, conf])
    # 格式化 YOLO 检测结果，传入 DeepSORT 进行目标跟踪
    formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
    tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)
    #  遍历所有当前跟踪的目标
    for obj in tracked_objects:
        try: # 获取目标的边界框
            bbox = obj.to_tlbr()
        except AttributeError: # 若无 bbox，尝试使用上一次的
            bbox = last_bbox.get(obj.track_id, None)
            if bbox is None:
                continue
        x1, y1, x2, y2 = map(int, bbox)
        obj_id = int(obj.track_id)

        # -------------------------------------------处理 ID 变更检测---------------------------------------------
        matched_old_id = None
        for old_id, old_bbox in last_bbox.items():
            if old_id != obj_id:
                old_x1, old_y1, old_x2, old_y2 = old_bbox
                iou = (min(x2, old_x2) - max(x1, old_x1)) * (min(y2, old_y2) - max(y1, old_y1))
                iou /= ((x2 - x1) * (y2 - y1) + (old_x2 - old_x1) * (old_y2 - old_y1) - iou)
                if iou > 0.5:  # 交并比（IoU）大于0.5则认为是同一目标
                    matched_old_id = old_id
                    break
        # ------------------------------------记录 ID 变更日志------------------------------------------
        if matched_old_id and matched_old_id != obj_id:
            if matched_old_id not in id_map:
                id_map[matched_old_id] = obj_id
                log_event("id_change", matched_old_id, {"new_id": obj_id, "iou": iou})

        last_bbox[obj_id] = [x1, y1, x2, y2]
        active_ids.add(obj_id)
        last_seen[obj_id] = current_time

        frame_count[obj_id] = frame_count.get(obj_id, 0) + 1
        stay_time = frame_count[obj_id] / 30  # 假设30FPS
        # 绘制目标框
        color = (0, 0, 255) if stay_time > parking_threshold else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 违停检测
        if stay_time > parking_threshold and obj_id not in current_parking:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            filename = f"pictures/{timestamp}_id_{obj_id}.jpg"

            cv2.imwrite(filename, frame)
            log_event("parking", obj_id, {"image_path": filename, "first_detected": timestamp})
            current_parking[obj_id] = {"first_detected": timestamp, "image_path": filename}

    # 处理目标丢失，清除
    left_ids = [obj_id for obj_id in current_parking if current_time - last_seen.get(obj_id, 0) > tolerance]
    for obj_id in left_ids:
        log_event("left", obj_id, current_parking[obj_id])
        del current_parking[obj_id]
        frame_count.pop(obj_id, None)
        last_bbox.pop(obj_id, None)

    cv2.imshow("Vehicle Tracker", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
