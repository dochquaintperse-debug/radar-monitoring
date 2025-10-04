import serial
import time
import json
from threading import Thread
from . import radar_protocol
from .radar_protocol import EXPECTED_LOCK_RESPONSE, FRAME_HEADER, FRAME_TAIL
from .radar_protocol import SERIAL_PARAMS, BREATH_QUERY_CMD, parse_radar_frame

bridge_instance = None

class SerialToMQTTBridge:
    def __init__(self):
        self.serial_port = None
        self.running = False
        self.thread = None
        self.mqtt_client = None
        self.current_port = None
        self.connected_sensor_id = None
        self.command_queue = []
        self.training_mode = False

    def connect_mqtt(self):
        """连接到MQTT broker"""
        from .mqtt_client import get_mqtt_client
        if not self.mqtt_client:
            self.mqtt_client = get_mqtt_client()
        if not hasattr(self.mqtt_client, '_connected'):
            self.mqtt_client.connect()
            self.mqtt_client._connected = True

    def identify_sensor(self):
        """发送操作1的识别指令，确认传感器并设置ID"""
        if not self.serial_port or not self.serial_port.is_open:
            return False
            
        identify_cmd = bytes.fromhex("5359018000010F3D5443")
        expected_response = identify_cmd
        
        try:
            self.serial_port.write(identify_cmd)
            print(f"已发送传感器识别指令: {identify_cmd.hex()}")
            
            time.sleep(2)
            
            if self.serial_port.in_waiting > 0:
                response = self.serial_port.read(self.serial_port.in_waiting)
                print(f"收到传感器响应: {response.hex()}")
                
                if expected_response in response:
                    # 修复：使用统一的传感器ID格式
                    self.connected_sensor_id = f"R60ABD1_BREATH_{self.current_port}"
                    if hasattr(self.mqtt_client, 'set_current_sensor_id'):
                        self.mqtt_client.set_current_sensor_id(self.connected_sensor_id)
                        print(f"传感器识别成功，统一ID: {self.connected_sensor_id}")
                    return True
                else:
                    print(f"传感器响应不匹配，预期: {expected_response.hex()}, 实际: {response.hex()}")
            else:
                print("未收到传感器响应")
        except Exception as e:
            print(f"传感器识别失败: {str(e)}")
        return False

    def connect_serial(self, port):
        """连接串口并立即执行传感器识别"""
        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=SERIAL_PARAMS["baud_rate"],
                bytesize=SERIAL_PARAMS["bytesize"],
                stopbits=SERIAL_PARAMS["stopbits"],
                parity=SERIAL_PARAMS["parity"],
                timeout=2
            )
            self.current_port = port
            print(f"串口 {port} 已打开")
            
            # 预先设置传感器ID（即使识别失败也有默认值）
            self.connected_sensor_id = f"R60ABD1_BREATH_{port}"
            if hasattr(self.mqtt_client, 'set_current_sensor_id'):
                self.mqtt_client.set_current_sensor_id(self.connected_sensor_id)
            
            if self.serial_port.in_waiting > 0:
                raw_response = self.serial_port.read(self.serial_port.in_waiting)
                print(f"[连接阶段] 端口 {port} 响应: {raw_response.hex()}")

            # 执行传感器识别
            if not self.identify_sensor():
                print(f"警告：串口 {port} 已打开，但未识别到R60ABD1传感器，使用默认ID")
            
            return True
        except Exception as e:
            print(f"串口连接失败: {e}")
            return False

    def set_training_mode(self, enable):
        self.training_mode = enable
        print(f"[串口桥] 训练模式设置为: {enable}")

    def start(self):
        """启动桥接器"""
        self.running = True
        self.thread = Thread(target=self._read_serial, daemon=True)
        self.thread.start()

    def stop(self):
        """停止桥接器"""
        self.running = False
        if self.thread:
            self.thread.join()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None

    def start_sending_commands(self):
        """启动定时发送查询指令"""
        if hasattr(self, 'command_thread') and self.command_thread.is_alive():
            print("命令发送线程已在运行，无需重复启动")
            return
        
        def send_loop():
            print(f"开始条件性发送查询指令: {BREATH_QUERY_CMD.hex()}（每1秒一次）")
            
            while self.running and self.serial_port and self.serial_port.is_open:
                send_allowed = self.training_mode or \
                            (self.mqtt_client and self.mqtt_client.monitoring_mode and self.mqtt_client.normal_range is not None)
                
                if send_allowed:
                    try:
                        self.serial_port.write(BREATH_QUERY_CMD)
                        print(f"[{time.strftime('%H:%M:%S')}] 已发送查询指令（模式: {'训练' if self.training_mode else '监测'}）")
                    except Exception as e:
                        print(f"发送指令失败: {str(e)}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] 不满足发送条件，跳过")
                
                time.sleep(1)
        
        import threading
        self.command_thread = threading.Thread(target=send_loop, daemon=True)
        self.command_thread.start()

    def _read_serial(self):
        """读取串口数据并处理"""
        while self.running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    raw_data = self.serial_port.read(self.serial_port.in_waiting)
                    print(f"[串口接收] 原始数据（{len(raw_data)}字节）: {raw_data.hex().upper()}")
                    
                    if self.training_mode or (self.mqtt_client and self.mqtt_client.monitoring_mode):
                        frame_size = 10
                        for i in range(0, len(raw_data) - frame_size + 1, frame_size):
                            frame = raw_data[i:i+frame_size]
                            if FRAME_HEADER in frame[:2]:
                                parsed_data = parse_radar_frame(frame, self.current_port)
                                if parsed_data:
                                    print(f"[解析成功] 传感器ID: {parsed_data['sensor_id']}, 值: {parsed_data['value']}")
                                    self._process_data(parsed_data)
                    else:
                        parsed_data = parse_radar_frame(raw_data, self.current_port)
                        if parsed_data:
                            self._process_data(parsed_data)
                            
                time.sleep(0.01)
            except Exception as e:
                print(f"读取串口数据失败: {e}")
                time.sleep(1)

    def _process_data(self, data):
        """发布数据到MQTT"""
        sensor_id = data["sensor_id"]
        print(f"[准备发布] 传感器ID: {sensor_id}, 数据: {data['value']}")
        
        # 更新连接的传感器ID
        if sensor_id != self.connected_sensor_id:
            self.connected_sensor_id = sensor_id
            if hasattr(self.mqtt_client, 'set_current_sensor_id'):
                self.mqtt_client.set_current_sensor_id(sensor_id)

        # 发布呼吸数据
        self.mqtt_client.publish(
            f"radar/data/{sensor_id}",
            json.dumps({
                "type": "radar_data",  # 关键：添加type字段
                "sensor_id": sensor_id,
                "value": data["value"],
                "hex_value": data.get("hex_value", f"0x{data['value']:02X}"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "training_mode": self.training_mode
            })
        )
