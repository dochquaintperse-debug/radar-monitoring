import os
import sys
from django.apps import AppConfig
import threading

class RadarAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'radar_app'
    
    def ready(self):
        # 本地环境启动MQTT客户端
        if 'runserver' in sys.argv:
            print("💻 本地环境，启动MQTT客户端")
            from .mqtt_client import get_mqtt_client
            mqtt_client = get_mqtt_client()
            if not hasattr(mqtt_client, '_connected'):
                mqtt_client.connect()
                mqtt_client._connected = True
