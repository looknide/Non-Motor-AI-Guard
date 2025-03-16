import json
import os

# 确保输出目录存在
output_dir = "process_logs"
os.makedirs(output_dir, exist_ok=True)

# **存储最终数据**
id_mapping = {}  # 记录 ID 变更
parking_events = {}  # 记录停车事件
left_events = {}  # 记录离开事件

# **读取日志**
log_file = "events.log"
if not os.path.exists(log_file):
    print("日志文件 events.log 不存在！请检查。")
    exit()

with open(log_file, "r") as file:
    logs = [json.loads(line.strip()) for line in file.readlines()]

# **处理日志**
for log in logs:
    event_type = log["event_type"]
    obj_id = log["obj_id"]
    data = log["data"]

    # **处理 ID 变更**
    if event_type == "id_change":
        new_id = data["new_id"]
        id_mapping[obj_id] = new_id  # 记录 ID 映射
        # 递归找到最终 ID，避免链式变更
        while id_mapping.get(new_id, None):
            new_id = id_mapping[new_id]
        id_mapping[obj_id] = new_id  # 更新映射

    # **处理停车事件**
    elif event_type == "parking":
        real_id = id_mapping.get(obj_id, obj_id)  # 转换到最终 ID
        if real_id not in parking_events:
            parking_events[real_id] = {
                "first_detected": data["first_detected"],
                "image_path": data["image_path"]
            }

    # **处理离开事件**
    elif event_type == "left":
        real_id = id_mapping.get(obj_id, obj_id)  # 转换到最终 ID
        if real_id in parking_events:  # 只有先停车的目标才会离开
            left_events[real_id] = {
                "first_detected": data["first_detected"],
                "image_path": data["image_path"]
            }

# **整理最终输出**
final_logs = []
for obj_id, parking_data in parking_events.items():
    left_data = left_events.get(obj_id, None)  # 查找是否有离开事件

    final_logs.append({
        "obj_id": obj_id,
        "first_detected": parking_data["first_detected"],
        "image_path": parking_data["image_path"],
        "left_time": left_data["first_detected"] if left_data else None
    })

# **存储 JSON 数据**
final_output = os.path.join(output_dir, "final_event.json")
with open(final_output, "w") as f:
    json.dump(final_logs, f, indent=4)

print(f"处理完成，结果已存入 {final_output}")
