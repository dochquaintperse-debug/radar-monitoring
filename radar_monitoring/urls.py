"""
URL configuration for radar_monitoring project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.conf.urls.static import static
import os

def health_check(request):
    """健康检查端点"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'radar-monitoring',
        'port': os.environ.get('PORT', '8000'),
        'mode': 'gunicorn',
        'debug': settings.DEBUG
    })

def favicon_view(request):
    """返回空的 favicon 响应"""
    return HttpResponse(content_type="image/x-icon", status=200)

def root_redirect(request):
    """根路径重定向到雷达应用"""
    return JsonResponse({
        'message': '毫米波雷达监测系统',
        'status': 'running',
        'endpoints': {
            'dashboard': '/radar/',
            'api': '/radar/api/',
            'admin': '/admin/',
            'health': '/health/'
        }
    })

urlpatterns = [
    # 根路径
    path('', root_redirect, name='root'),
    
    # 管理后台
    path('admin/', admin.site.urls),
    
    # 雷达应用所有路由
    path('radar/', include('radar_app.urls')),
    
    # 健康检查
    path('health/', health_check, name='health_check'),
    
    # Favicon处理
    path('favicon.ico', favicon_view, name='favicon'),
]

# 开发环境静态文件服务
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
