from datetime import datetime
import os
import sys
import ssl
import certifi
import re

# 设置 SSL 证书路径
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['SSLKEYLOGFILE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# 禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import google.generativeai as genai
from PIL import Image
import pymysql
import requests
import logging
import os
from pathlib import Path
from io import BytesIO
from smb.SMBConnection import SMBConnection
import time
import json

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).resolve().parent
# 配置日志文件路径
LOG_FILE = CURRENT_DIR / 'vlm_service.log'

# 创建日志处理器
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8-sig')
console_handler = logging.StreamHandler()

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# DB_CONFIG = {
#     "host": "localhost",
#     "port": 3306,
#     "user": "root",
#     "password": "Qiu817527@",
#     "database": "nonmotor",
#     "charset": "utf8mb4"
# }
# 服务器的数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "zhq",
    "password": "zhq",
    "database": "nonmotor",
    "charset": "utf8mb4"
}
def init_db():
    """初始化数据库连接"""
    try :
        conn = pymysql.connect(**DB_CONFIG)
        print("数据库连接成功!")
        return conn
    except Exception as e:
        print(f"数据库连接失败:{str(e)}")
        return None

API_KEY = 'AIzaSyDURd1TitvdriPlsqpiCQ1Ie48tWgoNetk'
genai.configure(
    api_key=API_KEY,
    transport='rest'
)

# 代理设置（如果需要）
# os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
# os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'

# 构建强化版提示语（使用三重引号保持格式）
ANALYSIS_PROMPT = """
请详细分析这张图片，识别每个红色框上方的'ID：x Time:xx.xs'格式的字段，有几个框识别几个非机动车字段，告诉我是否发生车辆违章或者事故，注意，你需要自己判断是否违规，我给你的图片有违规的也有没违规的，事故类型有："
    "（1.停放位置违规：一占用盲道：非机动车停放在盲道上，阻碍视障人士通行。二侵占绿地：将车辆停放在道路绿地中，导致植被破坏，影响市容环境。三占用消防通道/应急区域：堵塞消防通道或医院、学校等应急场所周边道路。四在禁停区域停放：如人行道、机动车道、非机动车禁驶区等。\n"
    "2.停放方式违规：一无序码放：车辆随意停放导致道路拥堵，尤其在早晚高峰易引发剐蹭事故。二妨碍通行：未在指定停车点停放且阻碍其他车辆、行人通行。三废旧车辆长期占用公共空间：利用废弃非机动车占用车位，影响交通并存在安全隐患（如电池自燃风险）。\n"
    "3.其他违规行为：一非法改装车辆：如改装电动自行车动力装置，影响安全性能。二未悬挂或遮挡号牌：未按规定悬挂非机动车号牌或故意涂改。三车祸：与其他车辆发生车祸行为。）\n"
    "并提供你识别的ID，未识别到则是none，你只需要回复我回复格式的内容，不允许出现回复格式以外的内容，回复格式为：IDxx:yes/no"
)

"""


# 动态解析项目根目录（基于当前文件的相对路径）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 配置 requests 会话
session = requests.Session()
session.verify = False

def get_total_records():
    total = 0
    try:
        conn = init_db()
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) as count FROM `non_motor_vehicle`")
            result = cursor.fetchone()
        if result:
            total += result[0]
            print(f"[后端] 当前统计到的 track_id 数量：{total}")
        else:
            total = 0
            print("Error in get_total_track_ids:", e)
    except Exception as e:
        print("Error:", e)
    return total

def get_violation_records():
    total_count = get_total_records()
    current_time = datetime.now().strftime("%H:%M:%S")
    return [{
        "time": current_time,
        "count": total_count
    }]


def get_unprocessed_images():
    """获取未处理的图片记录"""
    conn=init_db()
    # conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            # 查询未处理的图片记录        conn = pymysql.connect(**DB_CONFIG)
            cursor.execute("""
                SELECT track_id, image_path 
                FROM non_motor_vehicle 
                WHERE is_illegal IS NULL 
                OR is_illegal = True
                ORDER BY track_id ASC
            """)
            results = cursor.fetchall()
            logger.info(f"查询到 {len(results)} 条未处理的图片记录")
            return results
    except Exception as e:
        logger.error(f"获取未处理图片失败: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def update_violation_status(track_id, violation_result):
    conn = None
    try:
        logger.info(f"开始更新违规状态，原始结果: {violation_result}")
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            pattern = re.compile(r'ID(\d+)\s*:\s*(yes|no)', re.IGNORECASE)
            results = violation_result.strip().split('\n')
            updated_ids = []

            for result in results:
                match = pattern.search(result)
                if not match:
                    logger.warning(f"跳过无效结果行: {result}")
                    continue

                try:
                    vehicle_id = int(match.group(1))  # 提取数字ID
                    status = match.group(2).lower()  # 提取状态
                    is_violation = status == 'yes'

                    logger.info(f"解析结果 → ID:{vehicle_id} 状态:{'违规' if is_violation else '合规'}")

                    # 增强存在性检查（带状态锁定）
                    cursor.execute("""
                        SELECT track_id 
                        FROM non_motor_vehicle 
                        WHERE track_id = %s 
                        AND (is_illegal IS NULL OR is_illegal != %s)
                        FOR UPDATE
                    """, (vehicle_id, is_violation))
                    if not cursor.fetchone():
                        logger.warning(f"ID {vehicle_id} 无状态变更或不存在")
                        continue
                    # 原子化更新操作
                    cursor.execute("""
                        UPDATE non_motor_vehicle 
                        SET is_illegal = %s
                        WHERE track_id = %s
                    """, (is_violation, vehicle_id))

                    if cursor.rowcount > 0:
                        updated_ids.append(vehicle_id)
                        logger.info(f"状态更新成功 → ID:{vehicle_id}")
                    else:
                        logger.warning(f"状态未变更 → ID:{vehicle_id}")

                except ValueError as ve:
                    logger.error(f"ID转换错误: {str(ve)}")
                except pymysql.Error as e:
                    logger.error(f"数据库操作异常: {str(e)}")

            conn.commit()
            logger.info(f"本次更新共处理 {len(updated_ids)} 条记录")
            return len(updated_ids) > 0

    except Exception as e:
        logger.error(f"更新违规状态失败: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def delete_compliant_records(track_id):
    """删除合规记录"""
    conn = None
    try:
        logger.info(f"准备删除合规记录: ID {track_id}")
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # 先检查记录是否存在
            cursor.execute("""
                SELECT COUNT(*) 
                FROM non_motor_vehicle 
                WHERE track_id = %s
            """, (track_id,))
            
            if cursor.fetchone()[0] == 0:
                logger.warning(f"ID {track_id} 在数据库中不存在")
                return
            
            # 检查是否为合规记录
            cursor.execute("""
                SELECT is_illegal 
                FROM non_motor_vehicle 
                WHERE track_id = %s
            """, (track_id,))
            
            result = cursor.fetchone()
            if not result or result[0] is None:
                logger.warning(f"ID {track_id} 的违规状态未设置")
                return
                
            if result[0]:
                logger.info(f"ID {track_id} 为违规记录，不删除")
                return
            
            # 执行删除操作
            cursor.execute("""
                DELETE FROM non_motor_vehicle 
                WHERE track_id = %s AND is_illegal = False
            """, (track_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"成功删除合规记录: ID {track_id}")
            else:
                logger.warning(f"删除合规记录失败: ID {track_id}")
                
    except Exception as e:
        logger.error(f"删除合规记录失败: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def delete_violation_records(track_id):
    """删除违停记录"""
    conn = None
    try:
        logger.info(f"准备删除违停记录: ID {track_id}")
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # 先检查记录是否存在
            cursor.execute("""
                SELECT COUNT(*) 
                FROM non_motor_vehicle 
                WHERE track_id = %s
            """, (track_id,))
            
            if cursor.fetchone()[0] == 0:
                logger.warning(f"ID {track_id} 在数据库中不存在")
                return
            
            # 检查是否为违停记录
            cursor.execute("""
                SELECT is_illegal 
                FROM non_motor_vehicle 
                WHERE track_id = %s
            """, (track_id,))
            
            result = cursor.fetchone()
            if not result or result[0] is None:
                logger.warning(f"ID {track_id} 的违规状态未设置")
                return
                
            if not result[0]:
                logger.info(f"ID {track_id} 为合规记录，准备删除")
                # 执行删除操作
                cursor.execute("""
                    DELETE FROM non_motor_vehicle 
                    WHERE track_id = %s AND is_illegal = False
                """, (track_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"成功删除合规记录: ID {track_id}")
                else:
                    logger.warning(f"删除合规记录失败: ID {track_id}")
                return
            
            # 执行删除操作
            cursor.execute("""
                DELETE FROM non_motor_vehicle 
                WHERE track_id = %s AND is_illegal = True
            """, (track_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"成功删除违停记录: ID {track_id}")
            else:
                logger.warning(f"删除违停记录失败: ID {track_id}")
                
    except Exception as e:
        logger.error(f"删除违停记录失败: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def verify_api_key():
    """验证API密钥是否有效"""
    try:
        logger.info("正在验证API密钥...")
        models = genai.list_models()
        logger.info("API密钥验证成功")
        return True
    except Exception as e:
        logger.error(f"API密钥验证失败: {str(e)}")
        return False

def fetch_image_path(image_id):
    """从数据库获取图片相对路径并验证有效性"""
    conn = None
    try:
        logger.info(f"正在获取图片ID {image_id} 的路径")
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT image_path FROM non_motor_vehicle WHERE track_id = %s",
                (image_id,)
            )
            if result := cursor.fetchone():
                raw_path = result[0]
                logger.info(f"获取到原始路径: {raw_path}")

                target_path = PROJECT_ROOT / raw_path
                target_path = target_path.resolve()

                if not target_path.exists():
                    logger.error(f"图片路径无效: {target_path}")
                    raise FileNotFoundError(f"图片路径无效: {target_path}")
                logger.info(f"成功获取有效图片路径: {target_path}")
                return str(target_path)
            logger.error(f"图片ID {image_id} 不存在")
            raise ValueError(f"图片ID {image_id} 不存在")

    except pymysql.MySQLError as e:
        logger.error(f"数据库错误: {str(e)}")
        raise
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"业务逻辑错误: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def load_image(source):
    """通用图片加载函数"""
    try:
        logger.info(f"正在加载图片: {source}")
        if source.startswith(('http://', 'https://')):
            response = requests.get(source, timeout=10)
            return Image.open(BytesIO(response.content))
        elif source.startswith('\\\\'):
            parts = source.split('\\')
            server_ip, share_name, file_path = parts[2], parts[3], '\\'.join(parts[4:])
            conn = SMBConnection('共享用户名', '共享密码', 'client_pc', server_ip)
            conn.connect(server_ip, 139)
            file_obj = BytesIO()
            conn.retrieveFile(share_name, file_path, file_obj)
            return Image.open(file_obj)
        else:
            return Image.open(source)  # 支持本地路径
    except Exception as e:
        logger.error(f"图片加载失败: {str(e)}")
        raise

def analyze_image(img):
    """执行图像分析,返回分析结果的文本字符串"""
    try:
        logger.info("开始图像分析")
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("模型加载成功，开始生成内容...")
        
        timeout = 30  # 30秒超时
        start_time = time.time()
        
        response = model.generate_content(
            [ANALYSIS_PROMPT, img],
            generation_config={
                "temperature": 0.4,
                "top_p": 1,
                "top_k": 32,
                "max_output_tokens": 2048,
                "stop_sequences": ["\n\n"],
            },
            safety_settings={
                "HARASSMENT": "block_none",
                "HATE_SPEECH": "block_none",
                "SEXUALLY_EXPLICIT": "block_none",
                "DANGEROUS": "block_none"
            }
        )
        
        if time.time() - start_time > timeout:
            raise TimeoutError("API调用超时")
        
        logger.info("图像分析完成")
        return response.text.strip()
    except TimeoutError as e:
        logger.error(f"图像分析超时: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"图像分析失败: {str(e)}")
        raise

def process_images():
    """处理所有未处理的图片"""
    try:
        # 获取未处理的图片
        unprocessed_images = get_unprocessed_images()
        if not unprocessed_images:
            logger.info("没有需要处理的图片")
            return

        logger.info(f"找到 {len(unprocessed_images)} 张未处理的图片")
        
        # 处理每张图片
        for track_id, image_path in unprocessed_images:
            try:
                logger.info(f"开始处理图片ID: {track_id}, 路径: {image_path}")
                full_path = PROJECT_ROOT / image_path # 获取完整图片路径
                if not full_path.exists():
                    logger.error(f"图片不存在: {full_path}")
                    continue
                
                # 加载并分析图片
                image = load_image(str(full_path))
                result = analyze_image(image)
                logger.info(f"图片分析结果: {result}")
                if not result or not any('ID' in line and ':' in line for line in result.split('\n')):
                    logger.error(f"无效的分析结果: {result}")
                    continue
                
                # 更新数据库
                is_violation = update_violation_status(track_id, result)
                logger.info(f"数据库更新状态: {'成功' if is_violation else '失败'}")
                
                # 检查是否需要删除记录
                if is_violation:
                    logger.info(f"检测到违停记录，准备删除: ID {track_id}")
                    delete_violation_records(track_id)
                else:
                    logger.info(f"检测到合规记录，准备删除: ID {track_id}")
                    delete_compliant_records(track_id)
                
                logger.info(f"图片ID {track_id} 处理完成")
                
            except Exception as e:
                logger.error(f"处理图片ID {track_id} 时出错: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"处理图片时出错: {str(e)}")
        raise

def start_monitoring(interval=5):
    """开始监控并处理新图片"""
    logger.info("开始监控新图片...")
    while True:
        try:
            process_images()
            logger.info(f"等待 {interval} 秒后继续检查...")
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("监控已停止")
            break
        except Exception as e:
            logger.error(f"监控过程中出错: {str(e)}")
            time.sleep(interval)

# 主流程
if __name__ == "__main__":
    try:
        logger.info("开始执行主程序")
        
        # 验证API密钥
        if not verify_api_key():
            raise ValueError("API密钥验证失败，请检查API密钥是否正确")
        
        # 开始监控新图片
        start_monitoring()
        
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        raise
    except KeyboardInterrupt:
        logger.info("操作已取消")