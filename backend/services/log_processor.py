import json
import time
from datetime import datetime
from ..database.models import db, NonMotorVehicle
import os
from pathlib import Path


def init_database():
    """
    初始化数据库
    """
    try:
        # 连接数据库
        db.connect()
        # 创建表
        db.create_tables([NonMotorVehicle])
        print("数据库初始化成功")
    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")
        raise e


def start_log_processor(log_file_path, check_interval=1):
    """
    持续监控日志文件并处理新事件
    """
    # 确保日志文件所在目录存在
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    if not os.path.exists(log_file_path):
        open(log_file_path, 'a').close()
    last_position = 0

    while True:
        try:
            with open(log_file_path, 'r') as f:
                # 获取文件当前大小
                f.seek(0, 2)
                current_position = f.tell()

                # 如果有新内容
                if current_position > last_position:
                    # 回到上次读取的位置
                    f.seek(last_position)

                    # 处理新内容
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            event_type = event.get('event_type')
                            obj_id = event.get('obj_id')
                            data = event.get('data', {})

                            if event_type == 'parking':
                                # 检查记录是否存在
                                existing_record = NonMotorVehicle.get_or_none(
                                    NonMotorVehicle.track_id == obj_id
                                )
                                image_path = data.get('image_path', '')
                                if not image_path:
                                    print(f"警告: 图片路径为空，跳过事件: {event}")
                                    continue
                                
                                if existing_record:
                                    # 如果记录存在，更新它
                                    existing_record.image_path = image_path
                                    existing_record.is_illegal = True
                                    existing_record.is_left = False
                                    existing_record.save()
                                    print(f"成功更新记录: ID={obj_id} image_path={image_path}")
                                else: # 如果记录不存在，创建新记录
                                    try:
                                        NonMotorVehicle.create(
                                            track_id=obj_id,
                                            image_path=image_path,
                                            is_illegal=True,
                                            is_left=False
                                        )
                                        print(f"成功创建到达记录: ID={obj_id} image_path={image_path}")
                                    except Exception as e:
                                        print(f"创建到达记录失败: ID={obj_id}, 错误: {str(e)}")

                            elif event_type == 'left':
                                image_path = data.get('image_path', '')
                                if not image_path:
                                    print(f"警告: 图片路径为空，跳过事件: {event}")
                                    continue

                                existing_record = NonMotorVehicle.get_or_none(
                                    NonMotorVehicle.track_id == obj_id
                                )
                                if existing_record:
                                    existing_record.is_left = True
                                    # 若 image_path 不一致，也更新一下
                                    if not existing_record.image_path:
                                        existing_record.image_path = image_path
                                    existing_record.save()
                                    print(f"成功更新离开状态: ID={obj_id} image_path={image_path}")
                                else:
                                    try:
                                        NonMotorVehicle.create(
                                            track_id=obj_id,
                                            image_path=image_path,
                                            is_illegal=True,
                                            is_left=True
                                        )
                                        print(f"成功创建离开记录: ID={obj_id} image_path={image_path}")
                                    except Exception as e:
                                        print(f"创建离开记录失败: ID={obj_id}, 错误: {str(e)}")


                        except json.JSONDecodeError as e:
                            print(f"无法解析JSON行: {line}, 错误: {str(e)}")
                            continue
                        except Exception as e:
                            print(f"处理事件时出错: {str(e)}")
                            continue
                    # 更新位置
                    last_position = current_position

            time.sleep(check_interval)

        except FileNotFoundError:
            print(f"找不到日志文件: {log_file_path}")
            time.sleep(check_interval)
        except Exception as e:
            print(f"监控日志文件时出错: {str(e)}")
            time.sleep(check_interval)


if __name__ == "__main__":
    # 初始化数据库
    init_database()

    # 启动日志处理器
    log_file_path = "../events.log"
    start_log_processor(log_file_path)