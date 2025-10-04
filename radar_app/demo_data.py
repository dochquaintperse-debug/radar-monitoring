import random
import time
import threading
from django.utils import timezone
from .models import RadarSensor

class DemoDataGenerator:
    def __init__(self):
        self.running = False
        self.thread = None
        
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._generate_data, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        
    def _generate_data(self):
        # 等待Django完全启动
        time.sleep(5)
        
        # 创建演示传感器
        sensor, created = RadarSensor.objects.get_or_create(
            name="R60ABD1_BREATH_DEMO",
            defaults={"display_name": "演示雷达传感器"}
        )
        
        from .mqtt_client import get_mqtt_client
        mqtt_client = get_mqtt_client()
        mqtt_client.set_current_sensor_id("R60ABD1_BREATH_DEMO")
        
        while self.running:
            try:
                # 生成模拟呼吸数据
                value = random.randint(15, 40)
                
                data = {
                    "sensor_id": "R60ABD1_BREATH_DEMO",
                    "value": value,
                    "hex_value": f"0x{value:02X}",
                    "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # 直接调用数据处理函数
                mqtt_client._handle_radar_data_sync(data)
                time.sleep(2)  # 每2秒生成一次数据
                
            except Exception as e:
                print(f"演示数据生成错误: {e}")
                time.sleep(5)

# 全局实例
demo_generator = DemoDataGenerator()
