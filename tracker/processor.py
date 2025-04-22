# tracker/processor.py
import os
import time
from config import PARKING_THRESHOLD, MIN_PARKING_DURATION
from utils.logger import log_event
from tracker.image_process import image_process


class FrameProcessor:
    def __init__(self):
        self.track_history = {}  # ID -> frame count
        self.current_parking = {}  # ID -> parking info
        self.image_processor = image_process()

    def process_frame(self, frame, tracked_objects):
        # 获取当前所有跟踪对象的 ID
        current_ids = {int(obj.track_id) for obj in tracked_objects if obj.is_confirmed() and obj.track_id is not None}

        # 检查是否有对象离开
        for obj_id in list(self.current_parking.keys()):
            if obj_id not in current_ids:
                self.handle_object_leaving(obj_id)

        # 处理当前帧中的每个跟踪对象
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
                self.track_history[obj_id] = {"frames": 0, "first_detected": time.time()}
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
        print(f"Checking illegal parking for ID: {obj_id}, stay time: {stay_time:.1f}s")  # Debug line
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
            print(f"Saving violation image to: {filename}")  # Debug line
            self.current_parking[obj_id]["image_saved"] = True
            first_detected = time.strftime("%Y-%m-%d_%H-%M-%S",
                                           time.localtime(self.track_history[obj_id]["first_detected"]))

            # Log the event with the relative path for the image
            log_event("parking", obj_id, {
                "image_path": f"pictures/{os.path.basename(filename)}",  # Save only the file name, not the full path
                "first_detected": first_detected
            })

    def handle_object_leaving(self, obj_id):
        # 如果对象离开，记录离开事件
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        if obj_id in self.current_parking:
            elapsed = time.time() - self.current_parking[obj_id]["start_time"]
            first_detected = time.strftime("%Y-%m-%d_%H-%M-%S",
                                           time.localtime(self.track_history[obj_id]["first_detected"]))
            log_event("left", obj_id, {
                "first_detected": first_detected,
                "image_path": f"pictures/{timestamp}_id_{obj_id}.jpg"
            })
            # # 从当前停车记录中移除该对象
            del self.current_parking[obj_id]
