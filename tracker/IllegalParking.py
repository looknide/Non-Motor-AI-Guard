import cv2
import json
import time
import fcntl
import os
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# 创建日志和图片目录
os.makedirs("logs", exist_ok=True)
os.makedirs("pictures", exist_ok=True)
EVENT_LOG = "logs/events.log"
if time.strftime("%H:%M") == "00:00" and os.path.exists(EVENT_LOG):
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
            f.write(json.dumps(event) + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# 加载 YOLO 模型，注意调整模型路径和参数
model = YOLO("models/yolov8n.pt")
# 根据需要调整 DeepSORT 参数
deepsort = DeepSort(max_age=80, n_init=3, nn_budget=200)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

parking_threshold = 2  # 违停阈值（秒）
tolerance = 3.0  # 目标丢失容忍时间（秒）

# 分离统计数据与位置信息
frame_count = {}  # 记录累计帧数
last_bbox = {}  # 记录上一次有效的 bbox
last_seen = {}  # 记录目标最后出现时间
current_parking = {}  # 当前违停目标

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    current_time = time.time()
    active_ids = set()

    # YOLO 检测
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
            # 修改类别过滤条件，根据需要扩展或调整
            if conf > 0.5 and cls in [1, 2, 3]:
                detections.append([x1, y1, x2, y2, conf])

    formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
    tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)
    print("Tracked Objects:", tracked_objects)

    for obj in tracked_objects:
        try:
            bbox = obj.to_tlbr()
        except AttributeError:
            bbox = last_bbox.get(obj.track_id, None)
            if bbox is None:
                continue
        x1, y1, x2, y2 = map(int, bbox)

        # 平滑处理：若存在上一次 bbox，则进行线性插值
        obj_id = int(obj.track_id)
        if obj_id in last_bbox:
            prev_bbox = last_bbox[obj_id]
            alpha = 0.7  # 平滑因子
            x1 = int(alpha * prev_bbox[0] + (1 - alpha) * x1)
            y1 = int(alpha * prev_bbox[1] + (1 - alpha) * y1)
            x2 = int(alpha * prev_bbox[2] + (1 - alpha) * x2)
            y2 = int(alpha * prev_bbox[3] + (1 - alpha) * y2)
        last_bbox[obj_id] = [x1, y1, x2, y2]

        active_ids.add(obj_id)
        last_seen[obj_id] = current_time

        # 更新累计帧数
        frame_count[obj_id] = frame_count.get(obj_id, 0) + 1
        stay_time = frame_count[obj_id] / 30  # 假设30FPS

        # 限制边界框在图像内，并可加入尺寸校正
        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        # 可加入尺寸微调，如下示例缩小10%
        x_center = (x1 + x2) // 2
        y_center = (y1 + y2) // 2
        new_width = int((x2 - x1) * 0.9)
        new_height = int((y2 - y1) * 0.9)
        x1 = max(0, x_center - new_width // 2)
        y1 = max(0, y_center - new_height // 2)
        x2 = min(w, x_center + new_width // 2)
        y2 = min(h, y_center + new_height // 2)

        # 绘制目标框和文本
        color = (0, 0, 255) if stay_time > parking_threshold else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
                    (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        if stay_time > parking_threshold and obj_id not in current_parking:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            filename = f"pictures/{timestamp}_id_{obj_id}.jpg"
            cv2.imwrite(filename, frame)
            log_event("parking", obj_id, {"image_path": filename, "first_detected": timestamp})
            current_parking[obj_id] = {"first_detected": timestamp, "image_path": filename}

    # 处理目标丢失
    left_ids = [obj_id for obj_id in current_parking if current_time - last_seen.get(obj_id, 0) > tolerance]
    for obj_id in left_ids:
        log_event("left", obj_id, current_parking[obj_id])
        del current_parking[obj_id]
        if obj_id in frame_count:
            del frame_count[obj_id]
        if obj_id in last_bbox:
            del last_bbox[obj_id]

    cv2.imshow("Vehicle Tracker", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
