import os
import sys
from django.apps import AppConfig
import threading

class RadarAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'radar_app'
    
    def ready(self):
        # 检测云环境 - 只保留Render检测
        if os.environ.get('RENDER'):
            print("🌐 检测到Render环境，启动演示模式")
            self._start_demo_mode()
            return
            
        # 本地环境启动完整功能
        if 'runserver' in sys.argv:
            print("💻 本地环境，启动MQTT客户端")
            from .mqtt_client import get_mqtt_client
            mqtt_client = get_mqtt_client()
            if not hasattr(mqtt_client, '_connected'):
                mqtt_client.connect()
                mqtt_client._connected = True
    
    def _start_demo_mode(self):
        """Render云环境演示模式"""
        try:
            from .demo_data import demo_generator
            demo_generator.start()
            print("✅ 演示模式已启动")
        except ImportError:
            print("⚠️ 演示模块导入失败")
