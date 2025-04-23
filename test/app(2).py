# server.py
from flask import Flask, jsonify, send_from_directory, request, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
import time
import hashlib
import json
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.', static_url_path='')
# CORS配置
CORS(app, resources={
    r"/get-violations": {
        "origins": "*",
        "methods": ["GET"],
        "allow_headers": ["Content-Type"]
    },
    r"/get-latest-data": {
        "origins": "*",
        "methods": ["GET"],
        "allow_headers": ["Content-Type"]
    }
})
app.secret_key = 'your-secret-key'  # 用于session加密

# 数据库配置
db_config = {
    'host': '10.135.79.111',
    'user': 'hqd',
    'password': 'Heqidan@123',
    'database': 'nonmotor'
}

# 模拟用户数据（用于测试）
USERS = {
    'admin': hashlib.md5('admin123'.encode()).hexdigest(),
    'user': hashlib.md5('user123'.encode()).hexdigest()
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# 获取所有表的总记录数
def get_total_records(cursor):
    # 获取所有表名
    cursor.execute("SHOW TABLES")
    tables = [table_info[f'Tables_in_{db_config["database"]}'] for table_info in cursor.fetchall()]

    total_records = 0
    for table in tables:
        try:
            # 获取每个表的记录数
            cursor.execute(f"SELECT COUNT(*) as count FROM `{table}`")
            result = cursor.fetchone()
            if result:
                total_records += result['count']
        except Exception as e:
            # 忽略错误，继续处理其他表
            continue

    return total_records

@app.route('/')
def index():
    return send_from_directory('.', 'login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            'status': 'error',
            'message': '用户名和密码不能为空'
        }), 400
    
    try:
        # 检查用户是否存在
        if username not in USERS:
            return jsonify({
                'status': 'error',
                'message': '用户未注册，请先注册'
            }), 401
        
        # 验证密码
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        if USERS[username] != hashed_password:
            return jsonify({
                'status': 'error',
                'message': '密码错误'
            }), 401
        
        # 登录成功
        session['username'] = username
        return jsonify({
            'status': 'success',
            'message': '登录成功'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': '服务器错误，请稍后重试'
        }), 500

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            'status': 'error',
            'message': '用户名和密码不能为空'
        }), 400
    
    try:
        # 检查用户名是否已存在
        if username in USERS:
            return jsonify({
                'status': 'error',
                'message': '用户名已存在'
            }), 400
        
        # 创建新用户
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        USERS[username] = hashed_password
        
        return jsonify({
            'status': 'success',
            'message': '注册成功'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': '注册失败，请稍后重试'
        }), 500

@app.route('/modified')
def modified():
    if 'username' not in session:
        return redirect('/')
    return send_from_directory('.', 'modified.html')

@app.route('/modified-ccode')
def modified_ccode():
    if 'username' not in session:
        return redirect('/')
    return send_from_directory('.', 'modified-code.html')

@app.route('/get-violations')
def get_violation_stats():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 获取当前数据库总记录数
        total_records = get_total_records(cursor)

        # 获取当前时间
        current_time = datetime.now()

        # 创建数据点
        data_point = {
            "time": current_time.strftime("%H:%M:%S"),
            "count": total_records
        }

        # 模拟过去的11个数据点，每个间隔5秒
        data_points = []
        for i in range(11, 0, -1):
            past_time = current_time - timedelta(seconds=i * 5)
            # 随机生成一个接近当前值的历史值
            variation = int(total_records * 0.03)  # 3%的变化
            past_count = max(0, total_records - variation * i + int(variation * i * 0.5))
            data_points.append({
                "time": past_time.strftime("%H:%M:%S"),
                "count": past_count
            })

        # 添加当前数据点
        data_points.append(data_point)

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "data": data_points,
            "timestamp": time.time()
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        })

@app.route('/get-latest-data')
def get_latest_data():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 获取当前数据库总记录数
        total_records = get_total_records(cursor)

        # 获取当前时间
        current_time = datetime.now()
        current_time_str = current_time.strftime("%H:%M:%S")

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "time": current_time_str,
            "count": total_records,
            "timestamp": time.time()
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        })

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({
        'status': 'success',
        'message': '已退出登录'11
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)