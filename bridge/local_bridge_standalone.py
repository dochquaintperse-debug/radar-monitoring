import sys
import os
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
        available_ports = []
        
        for port in ports:
            # 过滤串口
            if any(keyword in port.description.upper() for keyword in ["USB", "COM", "SERIAL"]):
                available_ports.append(port.device)
                
        return available_ports
    
    def test_radar_connection(self, port):
        """测试是否为雷达设备"""
        try:
            test_serial = serial.Serial(port, 115200, timeout=2)
            
            # 识别命令
            identify_cmd = b"\x53\x59\x01\x80\x00\x01\x0F\x3D\x54\x43"
            test_serial.write(identify_cmd)
            time.sleep(1)
            
            if test_serial.in_waiting > 0:
                response = test_serial.read(test_serial.in_waiting)
                print(f"端口 {port} 响应: {response.hex().upper()}")
                
                # 预期响应
                if identify_cmd in response:
                    test_serial.close()
                    return True
            
            test_serial.close()
            return False
            
        except Exception as e:
            print(f"端口 {port} 测试失败: {e}")
            return False
    
    def connect(self, port):
        """连接串口"""
        try:
            self.serial_port = serial.Serial(port, 115200, timeout=2)
            print(f"已连接串口: {port}")
            return True
        except Exception as e:
            print(f"连接串口失败: {e}")
            return False
    
    def send_to_cloud(self, data):
        """发送数据到云端"""
        try:
            response = requests.post(
                f"{self.cloud_url}/radar/api/radar-data/",
                json=data,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"数据发送成功: 值={data['value']}")
                return True
            else:
                print(f"云端响应错误: {response.status_code}")
                print(f"响应内容: {response.text[:100]}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"无法连接到云端: {self.cloud_url}")
            return False
        except requests.exceptions.Timeout:
            print("请求超时")
            return False
        except Exception as e:
            print(f"发送错误: {e}")
            return False
    
    def parse_radar_data(self, raw_data):
        """解析雷达数据"""
        if len(raw_data) != 10:
            return None
            
        # 检查帧头帧尾
        if raw_data[:2] != b"\x53\x59" or raw_data[-2:] != b"\x54\x43":
            return None
            
        # 检查是否为呼吸数据回复
        if raw_data[2:6] != b"\x81\x82\x00\x01":
            return None
            
        # 提取数值
        value = raw_data[6]
        return {
            "value": value,
            "hex_value": f"0x{value:02X}"
        }
    
    def run(self):
        """运行监控"""
        print("正在扫描串口...")
        ports = self.find_ports()
        
        if not ports:
            print("未发现可用串口")
            return
            
        print(f"发现串口: {ports}")
        
        # 查找雷达设备
        radar_port = None
        for port in ports:
            print(f" 测试端口 {port}...")
            if self.test_radar_connection(port):
                radar_port = port
                print(f"发现雷达设备: {port}")
                break
            else:
                print(f"端口 {port} 不是雷达设备")
        
        if not radar_port:
            print("未发现雷达设备")
            return
        
        # 连接雷达
        if not self.connect(radar_port):
            return
        
        print("开始数据传输...")
        print("按 Ctrl+C 停止")
        print("-" * 50)
        
        consecutive_errors = 0
        max_errors = 5
        
        try:
            while True:
                try:
                    # 查询命令
                    query_cmd = b"\x53\x59\x81\x82\x00\x01\x0F\xBF\x54\x43"
                    self.serial_port.write(query_cmd)
                    time.sleep(0.1)
                    
                    if self.serial_port.in_waiting >= 10:
                        raw_data = self.serial_port.read(10)
                        print(f"接收数据: {raw_data.hex().upper()}")
                        
                        parsed = self.parse_radar_data(raw_data)
                        if parsed:
                            cloud_data = {
                                "sensor_id": f"LOCAL_RADAR_{radar_port.replace('COM', '')}",
                                "value": parsed["value"],
                                "hex_value": parsed["hex_value"],
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            if self.send_to_cloud(cloud_data):
                                consecutive_errors = 0
                            else:
                                consecutive_errors += 1
                        else:
                            print("数据解析失败")
                    
                    if consecutive_errors >= max_errors:
                        print(f"连续 {max_errors} 次发送失败，请检查网络连接")
                        break
                    
                    time.sleep(1) 
                    
                except KeyboardInterrupt:
                    print("\n用户手动停止")
                    break
                except Exception as e:
                    print(f"运行时错误: {e}")
                    time.sleep(5)
                    
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                print("串口已关闭")
def main():
    print("雷达数据云端桥接器 v1.0")
    print("=" * 50)
    
    # 获取云端网址
    while True:
        cloud_url = input("输入网址: ").strip()
        
        if not cloud_url:
            print("网址不能为空")
            continue
            
        # 自动添加协议
        if not cloud_url.startswith(('http://', 'https://')):
            cloud_url = 'https://' + cloud_url
            
        print(f"目标云端: {cloud_url}")
        
        # 测试连接
        try:
            print("测试云端连接...")
            response = requests.get(cloud_url, timeout=10)
            if response.status_code == 200:
                print("云端连接正常")
                break
            else:
                print(f"云端响应异常: {response.status_code}")
                retry = input("是否继续？(y/n): ")
                if retry.lower() == 'y':
                    break
        except Exception as e:
            print(f"云端连接失败: {e}")
            retry = input("是否重新输入网址？(y/n): ")
            if retry.lower() != 'y':
                return
    
    # 启动桥接器
    bridge = SimpleBridge(cloud_url)
    bridge.run()
if __name__ == "__main__":
    main()