import os
import sys
from django.apps import AppConfig
import threading
bridge_instance = None
class RadarAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'radar_app'
    def ready(self):
        # 检测云环境，跳过串口相关初始化
        if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('HEROKU'):
            print("检测到云环境，启动演示模式")
            self._start_demo_mode()
            return
            
        # 判断是否为交互模式
        if 'shell' in sys.argv or 'test' in sys.argv:
            return
        # 本地环境启动MQTT客户端
        from .mqtt_client import get_mqtt_client
        mqtt_client = get_mqtt_client()
        if not hasattr(mqtt_client, '_connected'):
            mqtt_client.connect()
            mqtt_client._connected = True
    def _start_demo_mode(self):
        """云环境演示模式"""
        try:
            from .demo_data import demo_generator
            demo_generator.start()
            print("演示模式已启动")
        except ImportError:
            pass