# main.py
import base64
import asyncio
import cv2

from queue import Queue
frame_queue = Queue(maxsize=20)
from tracker.detector import Detector
from tracker.tracker import Tracker
from tracker.processor import FrameProcessor
from utils.file_utils import clean_old_images
from queue import Empty
import time
from datetime import datetime


def run_algorithm():
    frame_count = 0
    last_frame_time = None

    detector = Detector()
    tracker = Tracker()
    processor = FrameProcessor()

    print("算法线程启动，等待视频帧...")

    while True:
        try:
            frame = frame_queue.get(timeout=1)  # 超时避免挂死线程
            frame_count += 1
            last_frame_time = datetime.now()
            print(f"[{last_frame_time}] 收到第 {frame_count} 帧")

            detections = detector.detect_objects(frame)
            tracked_objects = tracker.track_objects(detections, frame)
            processed_frame = processor.process_frame(frame, tracked_objects)

            # 可选：显示图像，部署时一般关闭
            cv2.imshow("Vehicle Tracker", processed_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            success, buffer = cv2.imencode('.jpg', processed_frame)
            # if success:
            #     jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            #     await websocket.send_text(jpg_as_text)  # 回传给前端
            # else:
            #     print("⚠️ 图像编码失败")
            # clean_old_images()

        except Empty:
            if last_frame_time is None or (datetime.now() - last_frame_time).total_seconds() > 5:
                print(
                    f"[{datetime.now()}] 等待视频帧中... 尚未收到任何帧" if frame_count == 0 else f"[{datetime.now()}] 超过5秒未收到新帧")
            # 没有视频帧，继续等待
            continue

    cv2.destroyAllWindows()

# run_algorithm()