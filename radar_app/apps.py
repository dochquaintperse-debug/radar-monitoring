import os
import sys
from django.apps import AppConfig
import threading
class RadarAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'radar_app'
    
    def ready(self):
        # 只在本地环境且不是Render环境时启动MQTT客户端
        is_render = os.environ.get('RENDER') is not None
        
        if 'runserver' in sys.argv and not is_render:
            print("💻 本地环境，尝试启动MQTT客户端")
            try:
                from .mqtt_client import get_mqtt_client
                mqtt_client = get_mqtt_client()
                if not hasattr(mqtt_client, '_connected'):
                    mqtt_client.connect()
                    mqtt_client._connected = True
                print("✅ MQTT客户端启动成功")
            except ImportError:
                print("⚠️ MQTT依赖未安装，跳过MQTT客户端启动")
            except Exception as e:
                print(f"⚠️ MQTT客户端启动失败: {e}")
        else:
            print("🌐 云端环境或非runserver模式，跳过MQTT客户端")
