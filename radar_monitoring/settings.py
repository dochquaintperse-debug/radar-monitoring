import os
import dj_database_url
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-k!i#5$z1x6f80=&&9+&c!p@4n_%js7@qc2-rh#rh0kwr6qku4f')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# 环境检测 - 只保留Render和本地
IS_RENDER = os.environ.get('RENDER') is not None
IS_PRODUCTION = IS_RENDER

# ALLOWED_HOSTS配置
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]

# Render环境域名
if IS_RENDER:
    ALLOWED_HOSTS.extend([
        os.environ.get('RENDER_EXTERNAL_HOSTNAME', ''),
        '.onrender.com'
    ])

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

# 数据库配置 - 简化为Render PostgreSQL和本地MySQL
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
    # 本地开发：使用MySQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'radar_db',
            'USER': 'root',
            'PASSWORD': 'Jago114514',
            'HOST': 'localhost',
            'PORT': '3306',
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
    print("✅ 使用本地MySQL数据库")

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
    # 本地开发：使用Redis
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [('127.0.0.1', 6379)],
            },
        },
    }
    print("✅ 使用Redis通道层（本地）")

# CORS配置 - 移除Railway域名
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
print(f"🚀 Django配置（纯Render版）:")
print(f"   📊 调试模式: {DEBUG}")
print(f"   🌐 环境: {'Render生产' if IS_RENDER else '本地开发'}")
print(f"   💾 数据库: {'PostgreSQL' if IS_RENDER else 'MySQL'}")
print(f"   🔗 主机: {ALLOWED_HOSTS}")
