# tracker/tracker.py
# DeepSORT跟踪
from deep_sort_realtime.deepsort_tracker import DeepSort
from config import DEEPSORT_CONFIG

class Tracker:
    def __init__(self):
        self.deepsort = DeepSort(**DEEPSORT_CONFIG)

    def track_objects(self, detections, frame):
        """返回跟踪对象"""
        formatted_detections = [[[d[0], d[1], d[2], d[3]], d[4]] for d in detections]
        return self.deepsort.update_tracks(formatted_detections, frame=frame)

