import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-k!i#5$z1x6f80=&&9+&c!p@4n_%js7@qc2-rh#rh0kwr6qku4f')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
IS_RENDER = os.environ.get('RENDER') is not None
# ALLOWED_HOSTS
ALLOWED_HOSTS = ['*'] if DEBUG else [
    'localhost', '127.0.0.1', '.onrender.com', 'radar-monitoring.onrender.com'
]

# 生产环境配置
if not DEBUG:
    if os.environ.get('RENDER'):
        ALLOWED_HOSTS.extend([
            '.onrender.com',
            'radar-monitoring.onrender.com',
        ])
    
    # 其他生产环境域名
    custom_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    ALLOWED_HOSTS.extend([host.strip() for host in custom_hosts if host.strip()])
else:
    # 开发环境允许所有
    ALLOWED_HOSTS = ['*']

print(f"🌐 ALLOWED_HOSTS: {ALLOWED_HOSTS}")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'corsheaders',
    'radar_app.apps.RadarAppConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'radar_monitoring.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages', 
            ],
        },
    },
]

WSGI_APPLICATION = 'radar_monitoring.wsgi.application'
ASGI_APPLICATION = "radar_monitoring.asgi.application"

# 数据库配置
if IS_RENDER:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        DATABASES = {
            'default': dj_database_url.parse(database_url, conn_max_age=600, conn_health_checks=True)
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
# Channels配置
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}
# CORS配置
CORS_ALLOW_ALL_ORIGINS = DEBUG
# 国际化
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
# 静态文件
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# 生产环境安全设置
if IS_RENDER and not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
