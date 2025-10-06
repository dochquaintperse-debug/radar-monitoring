import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 可选加载环境变量（修复dotenv错误）
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ 已加载 .env 文件")
except ImportError:
    print("⚠️ python-dotenv 未安装，跳过 .env 文件加载")
except Exception as e:
    print(f"⚠️ .env 文件加载失败: {e}")

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-k!i#5$z1x6f80=&&9+&c!p@4n_%js7@qc2-rh#rh0kwr6qku4f')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# 环境检测 - 只保留Render和本地
IS_RENDER = os.environ.get('RENDER') is not None
IS_PRODUCTION = IS_RENDER

# ALLOWED_HOSTS配置
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'testserver',
    '0.0.0.0',
]

# 生产环境配置
if not DEBUG:
    # Render.com 部署
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

# 数据库配置 - 简化为Render PostgreSQL和本地SQLite
if IS_RENDER:
    # Render环境：使用PostgreSQL
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        DATABASES = {
            'default': dj_database_url.parse(
                database_url,
                conn_max_age=600,
                conn_health_checks=True,
            )
        }
        print("✅ 使用Render PostgreSQL数据库")
    else:
        # 容错：使用SQLite作为备用
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
        print("⚠️ 未找到DATABASE_URL，使用SQLite备用")
else:
    # 本地开发：改为SQLite避免MySQL依赖问题
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("✅ 使用本地SQLite数据库")

# Channels配置 - 简化
if IS_RENDER:
    # Render生产环境：使用内存通道层
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
    print("✅ 使用内存通道层（Render）")
else:
    # 本地开发：也使用内存层，避免Redis依赖
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
    print("✅ 使用内存通道层（本地）")

# CORS配置
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "https://*.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "ws://localhost:8000",
    "wss://*.onrender.com",
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# 国际化
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# 静态文件配置
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# 静态文件目录
STATICFILES_DIRS = []
if os.path.exists(BASE_DIR / "static"):
    STATICFILES_DIRS.append(BASE_DIR / "static")

# WhiteNoise 配置
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 确保 WhiteNoise 在 MIDDLEWARE 中
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# 渲染模式检测
RENDER_MODE = os.environ.get('RENDER_SERVICE_TYPE', 'web')
if RENDER_MODE == 'web':
    print("🌐 启动HTTP服务模式 (Gunicorn)")
elif RENDER_MODE == 'websocket':
    print("📡 启动WebSocket服务模式 (Daphne)")
else:
    print("🔧 默认模式启动")

print(f"🚀 当前服务类型: {RENDER_MODE}")

# 生产环境静态文件压缩
if IS_RENDER:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 生产环境安全设置
if IS_RENDER and not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if IS_RENDER else 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'radar_app': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# 启动信息
print("=" * 50)
print("🚀 Django 配置信息")
print(f"DEBUG: {DEBUG}")
print(f"IS_RENDER: {IS_RENDER}")
print(f"DATABASE ENGINE: {DATABASES['default']['ENGINE']}")
print(f"STATIC_URL: {STATIC_URL}")
print(f"STATIC_ROOT: {STATIC_ROOT}")
print(f"环境变量 PORT: {os.environ.get('PORT', '未设置')}")
print(f"环境变量 RENDER: {os.environ.get('RENDER', '未设置')}")
print("=" * 50)
