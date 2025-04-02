import time
import cv2
from utils.logger import log_event
from config import PARKING_THRESHOLD, MIN_PARKING_DURATION
from tracker.image_process import image_process  # 引入 Drawer 类


class FrameProcessor:
    def __init__(self):
        self.trackers = {}  # 存储目标的跟踪器
        self.track_history = {}  # 存储目标的历史信息
        self.current_parking = {}  # 存储违停信息的字典
        self.image_processor = image_process()

    def process_frame(self, frame, tracked_objects):
        """处理帧并使用 CSRT 进行稳定跟踪"""
        for obj in tracked_objects:
            try:
                bbox = obj.to_tlbr()  # 获取车辆的边界框 (top, left, bottom, right)
                obj_id = int(obj.track_id)  # 获取车辆的唯一ID
                bbox = tuple(map(int, bbox))  # 确保 bbox 为整数元组
            except:
                continue

            # 如果是新目标，初始化 CSRT 跟踪器
            if obj_id not in self.trackers:
                tracker = cv2.TrackerCSRT.create()
                x = int(bbox[0])  # left
                y = int(bbox[1])  # top
                w = int(bbox[2] - bbox[0])  # width
                h = int(bbox[3] - bbox[1])  # height
                tracker.init(frame, (x, y, w, h))
                self.trackers[obj_id] = tracker

                # 初始化目标的历史信息
                self.track_history[obj_id] = {"frames": 0}

            # 使用 CSRT 更新目标位置
            success, bbox = self.trackers[obj_id].update(frame)
            if not success:
                print(f"目标 {obj_id} 丢失，可能需要重新检测！")
                continue  # 如果跟踪失败，跳过这个目标

            bbox = tuple(map(int, bbox))
            self.track_history[obj_id]["frames"] += 1
            stay_time = self.track_history[obj_id]["frames"] / 30  # 计算停留时间（假设30FPS）

            # 绘制跟踪框
            self.draw_tracking_bbox(frame, obj_id, bbox, stay_time)

            # 违停检测
            if stay_time > PARKING_THRESHOLD:
                self.check_illegal_parking(frame, obj_id, bbox, stay_time)

        return frame

    def draw_tracking_bbox(self, frame, obj_id, bbox, stay_time):
        """绘制跟踪框并显示停留时间"""
        color = (0, 255, 0)  # 绿色 (B, G, R)
        label = f"ID: {obj_id} parking time: {stay_time:.1f} s"
        image_process.draw_bbox(frame, bbox, color, label)

    def check_illegal_parking(self, frame, obj_id, bbox, stay_time):
        """检查并处理违停事件"""
        if obj_id not in self.current_parking:
            self.current_parking[obj_id] = {"start_time": time.time(), "image_saved": False}

        elapsed = time.time() - self.current_parking[obj_id]["start_time"]

        if elapsed >= MIN_PARKING_DURATION:
            # 违停车辆用红色框，并标记"违停警告"
            color = (0, 0, 255)  # 红色
            label = f"ID: {obj_id} parking time: {stay_time:.1f} s -illegal Parking"
            image_process.draw_bbox(frame, bbox, color, label)  # 先画违停红框

            # 记录违停事件并截图
            if not self.current_parking[obj_id]["image_saved"]:
                filename = self.image_processor.save_violation_image(frame, bbox, obj_id)  # 保存截图
                self.current_parking[obj_id]["image_saved"] = True
                log_event("parking", obj_id, {"duration": elapsed, "image_path": filename})