import cv2
import time
from sort import sort  # 确保已安装sort算法模块

# 假设目标跟踪器初始化
tracker = sort()

# 假设停车区域是 [(x1, y1), (x2, y2)] 格式
parking_area = [(100, 100), (500, 500)]  # 合法停车区域

# 存储目标的停放时间
target_parking_time = {}


def start_parking_timer(target_id):
    target_parking_time[target_id] = time.time()


def stop_parking_timer(target_id):
    if target_id in target_parking_time:
        parked_duration = time.time() - target_parking_time[target_id]
        print(f"目标 {target_id} 停放时间: {parked_duration:.2f} 秒")
        del target_parking_time[target_id]


def is_illegal_parking(bbox, parking_area):
    x1, y1, x2, y2 = bbox
    area_x1, area_y1 = parking_area[0]
    area_x2, area_y2 = parking_area[1]

    if x1 >= area_x1 and y1 >= area_y1 and x2 <= area_x2 and y2 <= area_y2:
        return False  # 合法停车区域
    else:
        return True  # 违规停车区域


# 画出停车区域
def draw_parking_area(frame, parking_area):
    x1, y1 = parking_area[0]
    x2, y2 = parking_area[1]
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # 画出停车区域的矩形框


# 画出目标框
def draw_target(frame, bbox, target_id):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
    cv2.putText(frame, f"ID: {int(target_id)}", (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)


# 假设有一个检测目标的循环
def detect_and_track(frame):
    detections = []  # 存放目标检测结果
    # 假设通过某种方式检测到目标并获得其边界框 bbox 格式：[x1, y1, x2, y2]

    trackers = tracker.update(detections)  # 更新跟踪器

    for track in trackers:
        track_id, x1, y1, x2, y2 = track

        # 检查目标是否进入违规停车区域
        if is_illegal_parking([x1, y1, x2, y2], parking_area):
            if track_id not in target_parking_time:
                start_parking_timer(track_id)
            print(f"目标 {track_id} 违规停车！")
        else:
            if track_id in target_parking_time:
                stop_parking_timer(track_id)
                print(f"目标 {track_id} 离开了违规区域！")

        draw_target(frame, [x1, y1, x2, y2], track_id)  # 绘制目标框

    draw_parking_area(frame, parking_area)  # 绘制停车区域
    return frame


# 读取视频或摄像头
cap = cv2.VideoCapture('video.mp4')  # 这里是你的视频路径，可以替换为0来使用摄像头

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 检测并跟踪目标
    frame = detect_and_track(frame)

    # 显示帧
    cv2.imshow('Parking Detection', frame)

    # 按键 'q' 退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
