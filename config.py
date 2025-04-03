# config.py
# 配置参数（阈值、模型路径等）
import os

# 目录配置
LOG_DIR = "logs"
IMG_DIR = "pictures"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# 模型配置
YOLO_MODEL_PATH = "models/yolov8n.pt"

# 违停检测参数
PARKING_THRESHOLD = 2  # 秒 时间阈值
MIN_PARKING_DURATION = 5  # 秒 最小停车持续时间

# DeepSORT参数
DEEPSORT_CONFIG = {
    "max_age": 60,
    "n_init": 5,
    "nn_budget": 200,
    "max_iou_distance": 0.7
}
