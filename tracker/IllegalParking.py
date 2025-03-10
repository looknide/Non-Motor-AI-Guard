import cv2
import json
import time
import fcntl
import numpy as np
import os
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# 创建日志目录和图片存储目录
os.makedirs("logs", exist_ok=True)
os.makedirs("pictures", exist_ok=True)
EVENT_LOG = "logs/events.log"
# 每天零点轮转日志
if time.strftime("%H:%M") == "00:00" and os.path.exists(EVENT_LOG):
    os.rename(EVENT_LOG, f"logs/events_{time.strftime('%Y%m%d')}.log")

# 写日志函数（带文件锁）
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

# 加载 YOLO 模型
model = YOLO("models/yolov8n.pt")
# 初始化 DeepSORT（使用较高的max_age、n_init、nn_budget以适应场景）
deepsort = DeepSort(max_age=60, n_init=5, nn_budget=200)

# 打开摄像头
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

# 违停检测参数
parking_threshold = 2    # 违停时间阈值（秒）
tolerance = 1.0          # 目标丢失容忍时间（秒）
track_history = {}       # 记录目标累计出现帧数（用于计算停留时间）
current_parking = {}     # 记录当前违停的目标
last_seen = {}           # 记录每个目标最后出现的时间

# 加载已有 JSON 数据
json_file = "IllegalParkingLog.json"
parking_data = {}
if os.path.exists(json_file):
    try:
        with open(json_file, "r") as f:
            parking_data = json.load(f)
    except json.JSONDecodeError:
        parking_data = {}

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    current_time = time.time()
    active_ids = set()

    # YOLO 检测：将当前帧输入模型，获得检测结果
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
            # 只检测摩托车（或自行车），根据需要调整类别
            if conf > 0.5 and cls in [1, 3]:
                detections.append([x1, y1, x2, y2, conf])

    # 格式化检测数据：DeepSORT 要求格式 [[[x1,y1,x2,y2], conf], ...]
    formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
    print("Formatted Detections:", formatted_detections)
    tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)
    print("Tracked Objects:", tracked_objects)

    # 遍历跟踪对象，直接使用预测框，不再额外平滑
    for obj in tracked_objects:
        try:
            bbox = obj.to_tlbr()  # 获取 [x1, y1, x2, y2]
        except AttributeError:
            continue
        x1, y1, x2, y2 = map(int, bbox)
        obj_id = int(obj.track_id)
        active_ids.add(obj_id)
        last_seen[obj_id] = current_time

        # 限制边界框不超出图像尺寸
        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        # 更新累计帧数（计算停留时间）
        track_history[obj_id] = track_history.get(obj_id, 0) + 1
        stay_time = track_history[obj_id] / 30  # 假设30FPS

        # 绘制目标框，若停留时间超过阈值则用红色标注
        color = (0, 0, 255) if stay_time > parking_threshold else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
                    (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 如果违停条件满足且目标未记录，则保存截图并记录日志
        if stay_time > parking_threshold and obj_id not in current_parking:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            filename = f"pictures/{timestamp}_id_{obj_id}.jpg"
            cv2.imwrite(filename, frame)
            log_event("parking", obj_id, {"image_path": filename, "first_detected": timestamp})
            current_parking[obj_id] = {"first_detected": timestamp, "image_path": filename}

    # 检查目标是否丢失：如果目标在 tolerance 时间内未更新，则认为离场
    left_ids = [obj_id for obj_id in current_parking if current_time - last_seen.get(obj_id, 0) > tolerance]
    for obj_id in left_ids:
        log_event("left", obj_id, current_parking[obj_id])
        del current_parking[obj_id]
        if obj_id in track_history:
            del track_history[obj_id]

    # 更新 JSON 数据：将不在 active_ids 中的记录状态设为 "left"
    for obj_id in list(parking_data.keys()):
        if int(obj_id) not in active_ids:
            parking_data[obj_id]["status"] = "left"
    with open(json_file, "w") as f:
        json.dump(parking_data, f, indent=4)

    cv2.imshow("Non-Motor Vehicle Tracker", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()



# import cv2
# import json
# import time
# import fcntl
# import numpy as np
# import os
# from ultralytics import YOLO
# from deep_sort_realtime.deepsort_tracker import DeepSort
#
# # 创建日志目录和文件
# os.makedirs("logs", exist_ok=True)
# os.makedirs("pictures", exist_ok=True)
# EVENT_LOG = "logs/events.log"
#
#
# # -------------------------- 新增函数 --------------------------
# def clean_old_images():
#     """定期清理7天前的图片"""
#     MAX_AGE = 7 * 86400  # 7天（秒）
#     now = time.time()
#     for filename in os.listdir("pictures"):
#         filepath = os.path.join("pictures", filename)
#         if os.path.isfile(filepath) and (now - os.path.getctime(filepath)) > MAX_AGE:
#             os.remove(filepath)
#
#
# def is_stable_tracking(obj_id, current_bbox, track_history):
#     """检查跟踪稳定性（位移突变<50像素）"""
#     if obj_id not in track_history:
#         return True
#     last_bbox = track_history[obj_id]["bbox"]
#     # 计算中心点位移
#     dx = abs((current_bbox[0] + current_bbox[2]) / 2 - (last_bbox[0] + last_bbox[2]) / 2)
#     dy = abs((current_bbox[1] + current_bbox[3]) / 2 - (last_bbox[1] + last_bbox[3]) / 2)
#     return dx < 50 and dy < 50
#
#
# # 写日志的函数（带事件合并）
# pending_events = {}
#
#
# def log_event(event_type, obj_id, data=None):
#     global pending_events
#     # 合并连续重复事件
#     if obj_id in pending_events:
#         last_event = pending_events[obj_id]
#         if last_event["event_type"] == event_type and (time.time() - last_event["timestamp"]) < 5:
#             return
#
#     timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
#     event = {
#         "timestamp": timestamp,
#         "event_type": event_type,
#         "obj_id": obj_id,
#         "data": data or {}
#     }
#
#     with open(EVENT_LOG, "a") as f:
#         fcntl.flock(f, fcntl.LOCK_EX)
#         f.write(json.dumps(event) + "\n")
#         fcntl.flock(f, fcntl.LOCK_UN)
#
#     pending_events[obj_id] = {"event_type": event_type, "timestamp": time.time()}
#
#
# # -------------------------- 主程序 --------------------------
# model = YOLO("models/yolov8n.pt")
# deepsort = DeepSort(max_age=60, n_init=5, nn_budget=200)
#
# cap = cv2.VideoCapture(0)
# if not cap.isOpened():
#     print("摄像头未打开！")
#     exit()
#
# # 参数配置
# parking_threshold = 2  # 基础停留阈值（秒）
# min_parking_duration = 5  # 新增：最小有效违停时间（秒）
# track_history = {}  # 新增：记录轨迹稳定性
# current_parking = {}
# last_clean_time = time.time()
#
# while cap.isOpened():
#     ret, frame = cap.read()
#     if not ret:
#         break
#
#     active_ids = set()
#
#     # -------------------------- YOLO检测 --------------------------
#     results = model(frame)
#     detections = []
#     for result in results:
#         for box in result.boxes:
#             if len(box.xyxy) == 0:
#                 continue
#             x1, y1, x2, y2 = map(int, box.xyxy[0])
#             conf = float(box.conf[0].item())
#             cls = int(box.cls[0].item())
#             if conf > 0.5 and cls in [1, 3]:
#                 detections.append([x1, y1, x2, y2, conf])
#
#     # -------------------------- DeepSORT跟踪 --------------------------
#     if detections:
#         formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
#         tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)
#
#         for obj in tracked_objects:
#             try:
#                 bbox = obj.to_tlbr()
#                 obj_id = int(obj.track_id)
#             except:
#                 continue
#
#             # 轨迹稳定性检查
#             current_bbox = list(map(int, bbox))
#             if not is_stable_tracking(obj_id, current_bbox, track_history):
#                 continue
#
#             # 更新轨迹历史
#             track_history[obj_id] = {"bbox": current_bbox}
#             active_ids.add(obj_id)
#
#             # 计算停留时间（带稳定性补偿）
#             track_history[obj_id]["frames"] = track_history.get(obj_id, {}).get("frames", 0) + 1
#             stay_time = track_history[obj_id]["frames"] / 30  # 假设30FPS
#
#             # 绘制界面
#             color = (0, 255, 0)
#             cv2.rectangle(frame, (current_bbox[0], current_bbox[1]),
#                           (current_bbox[2], current_bbox[3]), color, 2)
#             cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
#                         (current_bbox[0], current_bbox[1] - 10),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
#
#             # -------------------------- 违停检测（带延迟触发）--------------------------
#             if stay_time > parking_threshold:
#                 # 首次触发时初始化计时器
#                 if obj_id not in current_parking:
#                     current_parking[obj_id] = {
#                         "start_time": time.time(),
#                         "image_saved": False
#                     }
#
#                 # 检查是否满足最小持续时间
#                 elapsed = time.time() - current_parking[obj_id]["start_time"]
#                 if elapsed >= min_parking_duration and not current_parking[obj_id]["image_saved"]:
#                     # 保存截图
#                     timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
#                     filename = f"pictures/{timestamp}_id_{obj_id}.jpg"
#                     cv2.imwrite(filename, frame)
#
#                     # 记录日志
#                     log_event("parking", obj_id, {
#                         "image_path": filename,
#                         "duration": elapsed
#                     })
#                     current_parking[obj_id]["image_saved"] = True
#
#                 # 绘制红色警告框
#                 cv2.rectangle(frame, (current_bbox[0], current_bbox[1]),
#                               (current_bbox[2], current_bbox[3]), (0, 0, 255), 2)
#                 cv2.putText(frame, "Illegal Parking!",
#                             (current_bbox[0], current_bbox[1] - 30),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
#
#     # -------------------------- 处理离开车辆 --------------------------
#     left_ids = [obj_id for obj_id in current_parking if obj_id not in active_ids]
#     for obj_id in left_ids:
#         if current_parking[obj_id]["image_saved"]:
#             log_event("left", obj_id, {
#                 "duration": time.time() - current_parking[obj_id]["start_time"]
#             })
#         del current_parking[obj_id]
#         del track_history[obj_id]
#
#     # -------------------------- 每小时清理图片 --------------------------
#     if time.time() - last_clean_time > 3600:
#         clean_old_images()
#         last_clean_time = time.time()
#
#     # 显示画面
#     cv2.imshow("Non-Motor Vehicle Tracker", frame)
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break
#
# cap.release()
# cv2.destroyAllWindows()