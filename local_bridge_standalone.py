import sys
import os
import serial
import serial.tools.list_ports
import requests
import time
import json
import threading
from datetime import datetime

class SimpleBridge:
    def __init__(self, cloud_url):
        self.cloud_url = cloud_url.rstrip('/')
        self.serial_port = None
        self.running = False
        
    def find_ports(self):
        """查找可用串口"""
        ports = serial.tools.list_ports.comports()
        available_ports = []
        
        for port in ports:
            if any(keyword in port.description.upper() for keyword in ["USB", "COM", "SERIAL"]):
                available_ports.append(port.device)
                
        return available_ports
    
    def test_radar_connection(self, port):
        """测试是否为雷达设备"""
        try:
            test_serial = serial.Serial(port, 115200, timeout=2)
            identify_cmd = b"\x53\x59\x01\x80\x00\x01\x0F\x3D\x54\x43"
            test_serial.write(identify_cmd)
            time.sleep(1)
            
            if test_serial.in_waiting > 0:
                response = test_serial.read(test_serial.in_waiting)
                print(f"端口 {port} 响应: {response.hex().upper()}")
                
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
        """发送数据到云端 - 增强错误处理"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.post(
                    f"{self.cloud_url}/radar/api/radar-data/",
                    json=data,
                    timeout=10,  # 增加超时时间
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'RadarBridge/1.0'
                    }
                )
                
                if response.status_code == 200:
                    print(f"✅ 数据发送成功: 值={data['value']}")
                    return True
                else:
                    print(f"❌ 云端响应错误: {response.status_code}")
                    print(f"响应内容: {response.text[:200]}")
                    
            except requests.exceptions.ConnectionError as e:
                print(f"🔗 连接错误 (尝试 {retry_count + 1}/{max_retries}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"⏱️  请求超时 (尝试 {retry_count + 1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                print(f"📡 发送错误: {e}")
                break
        
        return False
    
    def parse_radar_data(self, raw_data):
        """解析雷达数据"""
