# main.py
import cv2
from tracker.detector import Detector
from tracker.tracker import Tracker
from tracker.processor import FrameProcessor
from utils.file_utils import clean_old_images

def run_algorithm():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("摄像头未打开！")
        exit()

    detector = Detector()
    tracker = Tracker()
    processor = FrameProcessor()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect_objects(frame)
        tracked_objects = tracker.track_objects(detections, frame)
        processed_frame = processor.process_frame(frame, tracked_objects)

        cv2.imshow("Vehicle Tracker", processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        clean_old_images()

    cap.release()
    cv2.destroyAllWindows()

run_algorithm()