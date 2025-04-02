# tracker/detector.py
# YOLO目标检测
import cv2
from ultralytics import YOLO
from config import YOLO_MODEL_PATH

class Detector:
    def __init__(self):
        self.model = YOLO(YOLO_MODEL_PATH)

    def detect_objects(self, frame):
        """返回符合条件的检测目标"""
        results = self.model(frame)
        detections = []
        for result in results:
            for box in result.boxes:
                if len(box.xyxy) == 0:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0].item())
                cls = int(box.cls[0].item())
                if conf > 0.5 and cls in [1, 3]:  # 车辆类别
                    detections.append([x1, y1, x2, y2, conf])
        return detections
