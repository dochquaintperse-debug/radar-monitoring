import struct

# 1. 串口参数
SERIAL_PARAMS = {
    "baud_rate": 115200,
    "bytesize": 8,
    "stopbits": 1,
    "parity": "N",
    "timeout": 3
}

# 2. 协议帧结构
FRAME_HEADER = b"\x53\x59"  # 帧头 "53 59"
FRAME_TAIL = b"\x54\x43"    # 帧尾 "54 43"

# 3. 固定命令定义
BREATH_QUERY_CMD = bytes.fromhex("5359818200010FBF5443")  # 操作2：呼吸数值查询命令（修正为81 82）

def build_locking_cmd():
    """构建锁定指令，用于传感器识别（操作1）"""
    return bytes.fromhex("5359018000010F3D5443")

# 定义预期回复（操作1）
EXPECTED_LOCK_RESPONSE = build_locking_cmd()

def parse_radar_frame(raw_data, port=None):
    """解析呼吸检测数据，只处理特定回复格式（操作3）"""
    # 校验帧头帧尾
    if FRAME_HEADER not in raw_data[:2] or FRAME_TAIL not in raw_data[-2:]:
        return None
    
    # 检查长度是否符合要求 (10字节)
    if len(raw_data) != 10:
        return None
    
    # 关键修改：检查帧头后4字节是否为"81820001"（索引2-5）
    frame_body = raw_data[2:6]  # 提取帧头后的4字节（第3-6字节）
    if frame_body != b"\x81\x82\x00\x01":
        return None
    
    # 计算校验和
    # checksum = raw_data[7]
    # payload = raw_data[2:7]  # 从控制字到数据字段
    # calculated_checksum = sum(payload) & 0xFF
    # if checksum != calculated_checksum:
    #     return None
    
    # 提取呼吸数值x（操作3）- 修正为十六进制转十进制
    x_byte = raw_data[6:7]  # 获取第7个字节（索引6）
    x = struct.unpack('B', x_byte)[0]  # 正确解析为无符号字节值
    
    sensor_id = f"R60ABD1_BREATH_{port}" if port else "R60ABD1_BREATH"
    
    return {
        "sensor_id": sensor_id,
        "control_type": "breath_detection",
        "value": x,
        "hex_value": f"0x{x:02X}"  # 同时提供十六进制表示
    }