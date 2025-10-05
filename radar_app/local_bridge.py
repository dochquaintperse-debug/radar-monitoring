import requests
import serial
import time
import json
from radar_app.serial_scanner import SerialScanner
from radar_app.radar_protocol import parse_radar_frame, BREATH_QUERY_CMD
class CloudBridge:
    def __init__(self, cloud_url):
        self.cloud_url = cloud_url.rstrip('/')
        self.serial_port = None
        self.running = False
        
    def find_and_connect(self):
        """自动查找并连接雷达"""
        sensors = SerialScanner.find_sensors()
        if sensors:
            port = sensors[0]['port']
            return self.connect_serial(port)
        return False
        
    def connect_serial(self, port):
        """连接串口"""
        try:
            import serial
            self.serial_port = serial.Serial(
                port=port,
                baudrate=115200,
                timeout=2
            )
            print(f"✅ 已连接串口: {port}")
            return True
        except Exception as e:
            print(f"❌ 串口连接失败: {e}")
            return False
    
    def send_to_cloud(self, data):
        """发送数据到云端"""
        try:
            response = requests.post(
                f"{self.cloud_url}/api/radar-data/",
                json=data,
                timeout=5
            )
            print(f"📤 数据已发送: {data['value']}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ 发送失败: {e}")
            return False
    
    def start_monitoring(self):
        """开始监控"""
        self.running = True
        print("🚀 开始监控雷达数据...")
        
        while self.running:
            try:
                # 发送查询命令
                if self.serial_port and self.serial_port.is_open:
                    self.serial_port.write(BREATH_QUERY_CMD)
                    time.sleep(0.1)
                    
                    if self.serial_port.in_waiting > 0:
                        raw_data = self.serial_port.read(self.serial_port.in_waiting)
                        parsed = parse_radar_frame(raw_data, "LOCAL")
                        
                        if parsed:
                            # 发送到云端
                            cloud_data = {
                                "sensor_id": parsed["sensor_id"],
                                "value": parsed["value"],
                                "hex_value": parsed["hex_value"],
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            self.send_to_cloud(cloud_data)
                    
                time.sleep(1)  # 每秒查询一次
                
            except KeyboardInterrupt:
                print("\n⏹️ 用户停止监控")
                break
            except Exception as e:
                print(f"❌ 监控错误: {e}")
                time.sleep(5)
        
        self.stop()
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        print("🛑 监控已停止")
# 使用方式
if __name__ == "__main__":
    bridge = CloudBridge("https://radar-monitoring.onrender.com/")
    
    if bridge.find_and_connect():
        bridge.start_monitoring()
    else:
        print("❌ 未找到雷达设备")