"""
WSGI config for radar_monitoring project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radar_monitoring.settings')
application = get_wsgi_application()
# 添加调试信息
print("🚀 WSGI application initialized for Gunicorn")
