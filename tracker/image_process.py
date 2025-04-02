import os
import cv2
import time

class image_process:
    """负责图像处理"""

    def __init__(self):
        """初始化截图保存目录"""
        self.screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../pictures"))
        if not os.path.exists(self.screenshot_dir):  # 如果目录不存在，创建它
            os.makedirs(self.screenshot_dir)

    @staticmethod
    def draw_bbox(frame, bbox,color, label):

        x1, y1, x2, y2 = map(int, bbox)  # 确保坐标为整数

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def save_violation_image(self, frame, bbox, obj_id):
        filename = os.path.join(self.screenshot_dir, f"violation_{obj_id}_{int(time.time())}.jpg")
        cv2.imwrite(filename, frame)  # 直接保存整个帧
        print(f"违停截图已保存: {filename}")  # 打印日志
        return filename
