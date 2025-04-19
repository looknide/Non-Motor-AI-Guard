from datetime import datetime
import os
import cv2
import time



class image_process:
    """负责图像处理"""

    def __init__(self):
        """初始化截图保存目录"""
        # 图片保存目录在 tracker 同级目录下的 pictures 文件夹
        self.screenshot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../pictures"))
        if not os.path.exists(self.screenshot_dir):  # 如果目录不存在，创建它
            os.makedirs(self.screenshot_dir)

    @staticmethod
    def draw_bbox(frame, bbox,color, label):

        x1, y1, x2, y2 = map(int, bbox)  # 确保坐标为整数

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def save_violation_image(self, frame, bbox, obj_id):
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        # 文件名包括时间戳和对象 ID
        filename = os.path.join(self.screenshot_dir, f"{timestamp}_id_{obj_id}.jpg")
        cv2.imwrite(filename, frame)
        print(f"违停截图已保存: {filename}")
        return filename