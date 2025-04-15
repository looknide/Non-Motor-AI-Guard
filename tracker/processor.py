# tracker/processor.py

import time
from config import PARKING_THRESHOLD, MIN_PARKING_DURATION
from utils.logger import log_event
from tracker.image_process import image_process

class FrameProcessor:
    def __init__(self):
        self.track_history = {}            # ID -> frame count
        self.current_parking = {}          # ID -> parking info
        self.image_processor = image_process()

    def process_frame(self, frame, tracked_objects):
        for obj in tracked_objects:
            if not obj.is_confirmed() or obj.track_id is None:
                continue

            obj_id = int(obj.track_id)

            # 获取bbox坐标
            try:
                bbox = tuple(map(int, obj.to_tlbr()))  # (x1, y1, x2, y2)
            except:
                continue

            # 更新轨迹帧计数
            if obj_id not in self.track_history:
                self.track_history[obj_id] = {"frames": 0}
            self.track_history[obj_id]["frames"] += 1

            stay_time = self.track_history[obj_id]["frames"] / 30.0  # 假设30fps

            if stay_time > PARKING_THRESHOLD:
                self.check_illegal_parking(frame, obj_id, bbox, stay_time)
            else:
                self.draw_tracking_bbox(frame, obj_id, bbox, stay_time)

        return frame

    def draw_tracking_bbox(self, frame, obj_id, bbox, stay_time):
        color = (0, 255, 0)  # 绿色
        label = f"ID:{obj_id} | {stay_time:.1f}s"
        self.image_processor.draw_bbox(frame, bbox, color, label)

    def check_illegal_parking(self, frame, obj_id, bbox, stay_time):
        if obj_id not in self.current_parking:
            self.current_parking[obj_id] = {
                "start_time": time.time(),
                "image_saved": False
            }

        elapsed = time.time() - self.current_parking[obj_id]["start_time"]

        color = (0, 0, 255)  # 红色
        label = f"ID:{obj_id} | {stay_time:.1f}s - ILLEGAL"
        self.image_processor.draw_bbox(frame, bbox, color, label)

        if elapsed >= MIN_PARKING_DURATION and not self.current_parking[obj_id]["image_saved"]:
            filename = self.image_processor.save_violation_image(frame, bbox, obj_id)
            self.current_parking[obj_id]["image_saved"] = True
            log_event("parking", obj_id, {
                "duration": elapsed,
                "image_path": filename
            })
