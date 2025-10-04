"""
ASGI config for radar_monitoring project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 1. 手动设置环境变量并初始化Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radar_monitoring.settings')
django.setup()  # 关键：确保应用加载完成

# 2. 初始化后再导入路由（避免提前导入导致的错误）
import radar_app.routing

# 3. 配置ASGI应用
application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # 处理HTTP请求
    "websocket": AuthMiddlewareStack(  # 处理WebSocket请求
        URLRouter(
            radar_app.routing.websocket_urlpatterns  # 加载路由
        )
    ),
})

