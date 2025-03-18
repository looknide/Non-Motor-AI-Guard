import cv2
import time
from tracker import process_frame

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("摄像头未打开！")
    exit()

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    processed_frame = process_frame(frame)  # 处理当前帧

    cv2.imshow("Vehicle Tracker", processed_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
