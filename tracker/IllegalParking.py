import cv2
import json
import time
import numpy as np
import os
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# 加载模型
model = YOLO("models/yolov8n.pt")

# 初始化DeepSORT
deepsort = DeepSort(max_age=30, n_init=3, nn_budget=100) #max_age=30：当目标连续 30 帧未被检测到时，会被认为丢失；n_init=3：目标需要连续 3 帧检测到后才确认跟踪；nn_budget=100：保留的外观特征（用于匹配）的最大数量。



# 打开摄像头
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

# 违停检测参数
parking_threshold = 2  # 停留时间阈值（秒）
track_history = {}  # 记录目标的停留时间

# 加载 JSON 文件
json_file = "IllegalParkingLog.json"
parking_data = {}
if os.path.exists(json_file):
    try:
        with open(json_file, "r") as f:
            parking_data = json.load(f)
    except json.JSONDecodeError:
        parking_data = {}

while cap.isOpened(): # 循环读取摄像头视频帧
    ret, frame = cap.read()
    if not ret: # 是否成功读取
        break

    active_ids = set()

    # YOLOv8 检测
    results = model(frame) # 当前帧 frame 输入 YOLO 模型，获得检测结果存于 results
    detections = []

    # 处理检测结果
    for result in results:
        for box in result.boxes:
            if len(box.xyxy) == 0:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0].item())
            cls = int(box.cls[0].item())
            cls_name = model.names[cls]  # 获取类别名称

            # 打印检测到的类别（调试用）
            print(f"检测到: {cls_name} (置信度={conf:.2f})")

            # 只检测摩托车（假设电动车被归类为 motorbike，cls=3）
            if conf > 0.5 and cls in [1,3]:  # 放宽阈值
                detections.append([x1, y1, x2, y2, conf])

    # DeepSORT 跟踪
    if detections:
        # 确保 detections 是 numpy 数组
        if isinstance(detections, np.ndarray):
            formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections.tolist()]
        else:
            formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
        print("Formatted Detections:", formatted_detections)  # 调试输出
        tracked_objects = deepsort.update_tracks(formatted_detections, frame=frame)
        print("Tracked Objects:", tracked_objects)



        for obj in tracked_objects:
            # 使用 to_tlbr() 方法获取边界框
            try:
                bbox = obj.to_tlbr()  # 返回 [x1, y1, x2, y2]
            except AttributeError:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            obj_id = int(obj.track_id)
            active_ids.add(obj_id)


            # 记录目标出现的时间
            if obj_id in track_history:
                track_history[obj_id] += 1
            else:
                track_history[obj_id] = 1

            # 记录停留时间
            track_history[obj_id] = track_history.get(obj_id, 0) + 1
            stay_time = track_history[obj_id] / 30  # 假设30FPS

            # **绘制目标框**
            color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"ID: {obj_id} Time: {stay_time:.1f}s",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # **违停检测（超过阈值标红）**
            if stay_time > parking_threshold:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "Illegal Parking!", (x1, y1 - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())  # 获取当前时间戳

    # 更新 JSON 数据
    for obj_id in list(parking_data.keys()):
        if int(obj_id) not in active_ids:
            parking_data[obj_id]["status"] = "left"

    # 写入文件
    with open(json_file, "w") as f:
        json.dump(parking_data, f, indent=4)

    # 显示画面
    cv2.imshow("Non-Motor Vehicle Tracker", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()