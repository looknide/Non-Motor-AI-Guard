import cv2
import torch
import json
import time
import numpy as np
import os
from ultralytics import YOLO
from sort.sort import Sort  # SORT目标跟踪

# 加载YOLOv8模型（轻量级）
model = YOLO("models/yolov8n.pt")
tracker = Sort()  # 初始化SORT跟踪器

# 设置摄像头
cap = cv2.VideoCapture(0)

# 违停检测参数
parking_threshold = 2  # 停留时间阈值（秒）
track_history = {}  # 记录目标的停留时间

# **尝试加载已有的 JSON 文件**
json_file = "IllegalParkingLog.json"
if os.path.exists(json_file):
    with open(json_file, "r") as f:
        try:
            parking_data = json.load(f)  # 读取已有数据
        except json.JSONDecodeError:
            parking_data = {}  # 解析失败时，创建空字典
else:
    parking_data = {}  # 文件不存在时，创建空字典

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    active_ids = set()

    # YOLOv8 目标检测
    results = model(frame)

    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])  # 获取边界框坐标
            conf = box.conf[0].item()  # 置信度
            cls = int(box.cls[0].item())  # 类别索引

            # **检测非机动车（自行车1, 摩托车3）**
            if conf > 0.5 and cls in [1, 3]:
                detections.append([x1, y1, x2, y2, conf])

    # **进行目标跟踪**
    if detections:
        detections = np.array(detections)
        tracked_objects = tracker.update(detections)

        active_ids = set()  # 记录当前帧仍可见的车辆 ID

        for obj in tracked_objects:
            x1, y1, x2, y2, obj_id = map(int, obj)
            active_ids.add(obj_id)  # 记录当前帧的 ID

            # 记录目标出现的时间
            if obj_id in track_history:
                track_history[obj_id] += 1
            else:
                track_history[obj_id] = 1

            # 停留时间换算成秒（假设摄像头30FPS）
            stay_time = track_history[obj_id] / 30

            # **绘制目标框**
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # **违停检测（超过阈值标红）**
            if stay_time > parking_threshold:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "Illegal Parking!", (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())  # 获取当前时间戳

                # **更新 JSON 记录**
                parking_data[str(obj_id)] = {
                    "object_id": obj_id,
                    "stay_time": round(stay_time, 1),
                    "threshold": parking_threshold,
                    "timestamp": timestamp,
                    "bounding_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "status": "active"  # 车辆仍然在场
                }

                print(f"车辆 {obj_id} 违停数据更新：", parking_data[str(obj_id)])

    # **遍历 JSON 数据，更新状态**
    for obj_id in parking_data.keys():
        obj_id_int = int(obj_id)
        if obj_id_int not in active_ids:
            parking_data[obj_id]["status"] = "left"  # 标记为离开
            print(f"车辆 {obj_id} 已离开，但数据保留")

    # **写入 JSON 文件**
    with open(json_file, "w") as f:
        json.dump(parking_data, f, indent=4)

    # 显示处理后的视频流
    cv2.imshow("Non-Motor Vehicle Tracker", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
