import sys
import os
# 添加依赖库到路径
sys.path.append(os.path.dirname(__file__))
# 简化版本，减少依赖
import serial
import serial.tools.list_ports
import requests
import time
import json
class SimpleBridge:
    def __init__(self, cloud_url):
        self.cloud_url = cloud_url.rstrip('/')
        self.serial_port = None
        
    def find_ports(self):
        """查找可用串口"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports if "USB" in port.description or "COM" in port.device]
    
    def connect(self, port):
        """连接串口"""
        try:
            self.serial_port = serial.Serial(port, 115200, timeout=2)
            print(f"✅ 已连接: {port}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def run(self):
        """运行监控"""
        ports = self.find_ports()
        print(f"🔍 发现串口: {ports}")
        
        for port in ports:
            if self.connect(port):
                print("🚀 开始发送数据到云端...")
                
                while True:
                    try:
                        # 发送查询命令
                        self.serial_port.write(b"\x53\x59\x81\x82\x00\x01\x0F\xBF\x54\x43")
                        time.sleep(0.1)
                        
                        if self.serial_port.in_waiting >= 10:
                            data = self.serial_port.read(10)
                            if len(data) == 10 and data[:2] == b"\x53\x59":
                                value = data[6]
                                
                                # 发送到云端
                                payload = {
                                    "sensor_id": f"LOCAL_RADAR_{port}",
                                    "value": value,
                                    "hex_value": f"0x{value:02X}",
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                                }
                                
                                try:
                                    requests.post(
                                        f"{self.cloud_url}/api/radar-data/",
                                        json=payload,
                                        timeout=3
                                    )
                                    print(f"📤 发送数据: {value}")
                                except:
                                    print("❌ 网络错误")
                        
                        time.sleep(1)
                        
                    except KeyboardInterrupt:
                        print("\n⏹️ 用户停止")
                        break
                    except Exception as e:
                        print(f"❌ 错误: {e}")
                        time.sleep(5)
                break
if __name__ == "__main__":
    cloud_url = input("请输入您的Render应用网址: ").strip()
    if not cloud_url.startswith('http'):
        cloud_url = 'https://' + cloud_url
    
    bridge = SimpleBridge(cloud_url)
    bridge.run()