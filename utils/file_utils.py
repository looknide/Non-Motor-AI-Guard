# 文件管理（定期清理图片）
# utils/file_utils.py
import os
import time
from config import IMG_DIR

def clean_old_images(max_age=86400):  # 1天（秒）
    """删除一天前的图片"""
    now = time.time()
    for filename in os.listdir(IMG_DIR):
        filepath = os.path.join(IMG_DIR, filename)
        if os.path.isfile(filepath) and (now - os.path.getctime(filepath)) > max_age:
            os.remove(filepath)
