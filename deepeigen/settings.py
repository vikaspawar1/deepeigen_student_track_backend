"""
Django settings for the Deep Eigen project.

Contains all project-wide configuration including database settings, 
installed apps, middleware, authentication providers, and regional 
pricing/subscription settings.
"""

from pathlib import Path
from datetime import timedelta
import os
# import django_heroku
from dotenv import load_dotenv
load_dotenv()

import dj_database_url

import socket

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

################################
# Maintenance Mode
################################
# MAINTENANCE_MODE = int(os.environ.get("MAINTENANCE_MODE", 0))
MAINTENANCE_MODE = int(os.environ.get("MAINTENANCE_MODE", 0))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!

# SECRET_KEY = 'django-insecure-u8m+26$3i2tu@%)^k3sll=ay7l4h(_f0$o@m_))ri7!psnoj5z'
SECRET_KEY = os.getenv('SECRET_KEY') or 'django-insecure-u8m+26$3i2tu@%)^k3sll=ay7l4h(_f0$o@m_))ri7!psnoj5z'



# DEBUG = False
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'  # Set DJANGO_DEBUG=True in local .env only




# Application definition
INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'djangocms_admin_style',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'admin_honeypot',
    'teams',
    'contact',
    'course',
    'ckeditor',
    'discussion_forum',
    'django_extensions',
    'deepeigen',
    'storages',
    'dashboard',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'customplaylist',
    'subscriptions',
    'student_analytics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_session_timeout.middleware.SessionTimeoutMiddleware',
    'django_referrer_policy.middleware.ReferrerPolicyMiddleware',
    'deepeigen.middleware.MaintenanceModeMiddleware',
    'accounts.middleware.RestrictAdminHoneypotMiddleware'
]


CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://deepeigen-new-version-frontend.onrender.com"
]

# Add Render frontend URL if provided
frontend_url = os.environ.get('FRONTEND_URL')
if frontend_url:
    if frontend_url not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(frontend_url)


CORS_ALLOW_CREDENTIALS = True

SESSION_EXPIRE_SECONDS = 1000000

SESSION_EXPIRE_AFTER_LAST_ACTIVITY = True
SESSION_TIMEOUT_REDIRECT           = 'home'
REFERRER_POLICY                    = 'strict-origin-when-cross-origin'

ROOT_URLCONF = 'deepeigen.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'course.context_processors.course_list',
            ],
            'libraries':{
                'custom_tags': 'course.templatetags.custom_tags',
                'account_custom':'accounts.templatetags.account_custom'

            }
        },
    },
]

WSGI_APPLICATION = 'deepeigen.wsgi.application'

AUTH_USER_MODEL = 'accounts.Account'




# PostgreSQL from environment variables (including Render)
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
    }

    
elif 'RDS_HOSTNAME' in os.environ:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': os.environ['RDS_DB_NAME'],
            'USER': os.environ['RDS_USERNAME'],
            'PASSWORD': os.environ['RDS_PASSWORD'],
            'HOST': os.environ['RDS_HOSTNAME'],
            'PORT': os.environ['RDS_PORT'],
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
            'NAME': os.getenv('DB_NAME', os.path.join(BASE_DIR, 'db.sqlite3')),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
        }
    }



AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1000),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}



# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_L10N = True

USE_TZ = True

SOCKET_NAME = socket.gethostname()

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"


MEDIA_URL = '/media/'

MEDIA_ROOT = os.path.join(BASE_DIR, "media")

from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.ERROR: 'danger',

}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# EMAIL_BACKEND = 'django_smtp_ssl.SSLEmailBackend'
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND')
# EMAIL_HOST = 'smtpout.secureserver.net'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
# EMAIL_PORT = 465
# Local SMTP - Django
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')


EMAIL_USE_TLS = True




DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')




# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.zoho.in'
# EMAIL_PORT = 587

# EMAIL_HOST_USER = 'contact@deepeigen.com'
# EMAIL_HOST_PASSWORD = 'sEGdnQCfGF6W'
# EMAIL_USE_TLS = True
# DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# django_heroku.settings(locals())
# Comment 2023_02_20
# db_from_env = dj_database_url.config(conn_max_age=600)
# DATABASES['default'].update(db_from_env)

RAZORPAY_API_KEY = os.getenv('RAZORPAY_API_KEY')
RAZORPAY_API_SECRET_KEY = os.getenv('RAZORPAY_API_SECRET_KEY')

MERCHANT_KEY = os.getenv('MERCHANT_KEY')
MERCHANT_SALT = os.getenv('MERCHANT_SALT')
PAYU_MODE = 'Live'




# RAZORPAY_API_KEY = 'rzp_test_SC3habFpUn2zel'
# RAZORPAY_API_SECRET_KEY = 'M28KH5xOu1T27Vd6qQaxXOI2'

# MERCHANT_KEY = 'uJfakg'
# MERCHANT_SALT = 'qcuWzw7t'
# PAYU_MODE = 'LIVE'
# FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
# FRONTEND_URL = os.environ.get('https://deepeigen-frontend.onrender.com')


CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://deepeigen-new-version-frontend.onrender.com",
]

if frontend_url:
    if frontend_url not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(frontend_url)

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

# Add Render backend host if provided
render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_host:
    ALLOWED_HOSTS.append(render_host)

# Also support manual override via environment variable
extra_hosts = os.environ.get('ALLOWED_HOSTS')
if extra_hosts:
    ALLOWED_HOSTS.extend([host.strip() for host in extra_hosts.split(',')])


CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SAMESITE = "None"

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Always trust the forwarded proto header from Render's proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')