import os
import sys
from django.apps import AppConfig

class RadarAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'radar_app'
    
    def ready(self):
        is_render = os.environ.get('RENDER') is not None
        
        if 'runserver' in sys.argv and not is_render:
            try:
                from .mqtt_client import get_mqtt_client
                mqtt_client = get_mqtt_client()
                if not hasattr(mqtt_client, '_connected'):
                    mqtt_client.connect()
                    mqtt_client._connected = True
            except:
                pass
