"""
ASGI config for radar_monitoring project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radar_monitoring.settings')
# 确保Django应用正确初始化
django_asgi_app = get_asgi_application()
# 导入WebSocket路由
from radar_app.routing import websocket_urlpatterns
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
# 添加调试信息
print("🚀 ASGI application initialized with WebSocket support")
print(f"📡 WebSocket patterns: {websocket_urlpatterns}")

