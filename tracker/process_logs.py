import json
import os

def process_logs(log_file="logs/events.log", output_dir="logs/process_logs"):
    """处理日志文件，将停车、ID 变更、离开事件整理并存储为 JSON 文件"""
    os.makedirs(output_dir, exist_ok=True)

    # 存储最终数据
    id_mapping = {}  # 记录 ID 变更
    parking_events = {}  # 记录停车事件
    left_events = {}  # 记录离开事件

    # 读取日志
    if not os.path.exists(log_file):
        print(f"日志文件 {log_file} 不存在！")
        return None

    with open(log_file, "r") as file:
        logs = [json.loads(line.strip()) for line in file.readlines()]

    # 处理日志
    for log in logs:
        event_type = log["event_type"]
        obj_id = log["obj_id"]
        data = log["data"]

        # 处理 ID 变更
        if event_type == "id_change":
            new_id = data["new_id"]
            id_mapping[obj_id] = new_id  # 记录 ID 映射

            # 解决 ID 变更环
            visited = set()
            final_id = new_id
            while final_id in id_mapping:
                if final_id in visited:
                    break
                visited.add(final_id)
                final_id = id_mapping[final_id]
            for v in visited:
                id_mapping[v] = final_id

        # 处理停车事件
        elif event_type == "parking":
            real_id = id_mapping.get(obj_id, obj_id)
            if real_id not in parking_events:
                parking_events[real_id] = {
                    "first_detected": data["first_detected"],
                    "image_path": data["image_path"]
                }

        # 处理离开事件
        elif event_type == "left":
            real_id = id_mapping.get(obj_id, obj_id)
            if real_id in parking_events:
                left_events[real_id] = {
                    "first_detected": data["first_detected"],
                    "image_path": data["image_path"]
                }

    # 整理最终输出
    final_logs = [
        {
            "obj_id": obj_id,
            "first_detected": parking_data["first_detected"],
            "image_path": parking_data["image_path"],
            "left_time": left_events.get(obj_id, {}).get("first_detected")
        }
        for obj_id, parking_data in parking_events.items()
    ]

    # 存储 JSON 数据
    final_output = os.path.join(output_dir, "final_event.json")
    with open(final_output, "w") as f:
        json.dump(final_logs, f, indent=4)

    print(f"日志处理完成，结果已存入 {final_output}")
    return final_logs

if __name__ == "__main__":
    process_logs()
