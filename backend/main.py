import sys
import os
import asyncio
import cv2
from starlette.responses import HTMLResponse
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import threading
import time
import logging
from pathlib import Path
import signal
import numpy as np
from datetime import datetime
from run_algorithm import frame_queue

from run_algorithm import run_algorithm

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException,WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from backend.services.log_processor import start_log_processor, init_database
from backend.services.VLM import start_monitoring, verify_api_key
from backend.database.models import NonMotorVehicle, db

app = FastAPI()

app = FastAPI(
    title="非机动车违停监控系统API",
    description="提供非机动车违停数据查询接口",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class NonMotorVehicleModel(BaseModel):
    track_id: int
    image_path: str
    is_illegal: bool
    is_left: bool
    update_time: datetime

class Config:
    orm_mode = True  # ORM模式允许直接从ORM对象转换



# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).resolve().parent
# # 配置日志文件路径
LOG_FILE = CURRENT_DIR / 'main_service.log'


# 挂载静态文件目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PICTURES_DIR = PROJECT_ROOT / "pictures"
app.mount("/static/pictures", StaticFiles(directory=str(PICTURES_DIR)), name="pictures")
# FRONTEND_DIR = PROJECT_ROOT / "frontend"
# app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
app.mount("/static/pictures", StaticFiles(directory=str(PICTURES_DIR)), name="pictures")

# uvicorn main:app --port 63342 --reload
# @app.get("/")
# async def get():
#     index_path = FRONTEND_DIR / "index.html"
#     if not index_path.exists():
#         raise HTTPException(status_code=404, detail="index.html 不存在")
#     return HTMLResponse(index_path.read_text(encoding="utf-8"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket 请求接收中...")
    await websocket.accept()
    print("WebSocket 连接已建立")
    asyncio.create_task(run_algorithm(frame_queue, websocket))

    while True:
        try:
            data = await websocket.receive_bytes()
            # print(f"收到视频帧，大小: {len(data)} 字节")
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame_queue.full():
                frame_queue.get()  # 丢掉旧帧
            frame_queue.put(frame)

        except Exception as e:
            print(f"WebSocket接收错误: {e}，断开连接")
            break

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8-sig'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def start_vlm_service():
    """启动VLM服务"""
    try:
        # 验证API密钥
        if not verify_api_key():
            raise ValueError("API密钥验证失败，请检查API密钥是否正确")

        logger.info("VLM服务API密钥验证成功")
        # 开始监控新图片
        start_monitoring()
    except Exception as e:
        logger.error(f"VLM服务启动失败: {str(e)}")
        raise



def start_backend_service():
    try:
        logger.info("开始启动后端服务...")
        logger.info("正在初始化数据库...")
        init_database()
        logger.info("数据库初始化完成")

        # 启动 run_algorithm 函数的线程
        logger.info("正在启动算法...")
        algorithm_thread = threading.Thread(target=run_algorithm, daemon=True)
        algorithm_thread.start()
        logger.info("算法启动成功")

        # 启动日志处理器线程
        logger.info("正在启动日志处理器...")
        log_processor_thread = threading.Thread(
            target=start_log_processor,
            args=("../events.log",),
            daemon=True
        )
        log_processor_thread.start()
        logger.info("日志处理器启动成功")

        # 启动VLM服务线程
        logger.info("正在启动VLM服务...")
        vlm_thread = threading.Thread(
            target=start_vlm_service,
            daemon=True
        )
        vlm_thread.start()
        logger.info("VLM服务启动成功")
        logger.info("所有服务已启动，正在运行中...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n正在关闭后端服务...")

    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        raise
should_exit = threading.Event()

def run_api_server():
    uvicorn.run(app, host="0.0.0.0", port=8085)

def signal_handler(sig, frame):
    print("\n正在停止所有服务...")
    should_exit.set()
    time.sleep(2)
    sys.exit(0)


def run_backend():
    """运行后端服务"""
    start_backend_service()

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("\n==== 非机动车违停监控系统 - 一体化启动 ====\n")
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 启动后端服务
            backend_future = executor.submit(run_backend)
            time.sleep(3)
            # 启动API服务
            api_future = executor.submit(run_api_server)

            print("\n所有服务已启动！")
            print("1. 浏览器直接打开 frontend/index.html")
            print("2. 访问 http://localhost:8085/frontend/index.html")
            print("3. 访问 http://localhost:8085/ (自动重定向)")
            print("API文档：http://localhost:8085/docs")

            # 等待服务完成（通常不会自然完成，除非出错）
            backend_future.result()
            api_future.result()

    except KeyboardInterrupt:
        print("\n接收到中断信号，正在关闭服务...")
    except Exception as e:
        print(f"\n发生错误：{str(e)}")
    finally:
        # 确保所有线程都能正常退出
        should_exit.set()

if __name__ == "__main__":
    main()