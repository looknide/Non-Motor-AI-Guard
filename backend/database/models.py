from datetime import datetime
from peewee import *
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 使用MySQL配置
db = MySQLDatabase(
    'nonmotor',  # 数据库名称
    user='root',  # MySQL用户名
    password='Qiu817527@',  # MySQL密码
    host='localhost',  # 本地主机
    port=3306,  # MySQL默认端口
    charset='utf8mb4'  # 使用utf8mb4字符集
)

def init_db():
    """初始化数据库连接"""
    try:
        db.connect()
        print("数据库连接成功！")
        return True
    except Exception as e:
        print(f"数据库连接失败: {str(e)}")
        return False

class NonMotorVehicle(Model):
    track_id = IntegerField(primary_key=True)  # 使用算法生成的UUID
    image_path = TextField(default=datetime.now)
    is_illegal = BooleanField()
    is_left = BooleanField()

    class Meta:
        database = db
        table_name = 'non_motor_vehicle'  # 指定表名
        indexes = (
            (('is_illegal', 'is_left'), False),  # 复合索引
        )

# 创建表
def create_tables():
    """创建数据库表"""
    try:
        db.create_tables([NonMotorVehicle])
        print("数据库表创建成功！")
    except Exception as e:
        print(f"创建数据库表失败: {str(e)}")

if __name__ == "__main__":
    if init_db():
        create_tables()