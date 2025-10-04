from django.urls import re_path
from . import consumers

# 关键：使用^和$确保路径精确匹配，避免模糊匹配问题
websocket_urlpatterns = [
    re_path(r'^ws/radar/$', consumers.RadarConsumer.as_asgi()),
]
    
