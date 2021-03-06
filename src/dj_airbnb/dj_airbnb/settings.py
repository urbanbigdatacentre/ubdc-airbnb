"""
Django settings for dj_airbnb project.

Generated by 'django-admin startproject' using Django 3.1.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import os
import sys
import sysconfig
from pathlib import Path

from socket import gethostbyname, gaierror


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# conda default gdal location on Windows, should not matter for Unix
_GDAL_LIBRARY_PATH = Path(Path(sysconfig.get_paths()["data"]) / "Library/bin" / "gdal300.dll")
if _GDAL_LIBRARY_PATH.is_file():
    GDAL_LIBRARY_PATH = _GDAL_LIBRARY_PATH.as_posix()


SECRET_KEY = '!@%ff)awnl(dx)6!!$zrdd9=l_6b76vl+*pw2jj54vljjiz2-y'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", 'True').lower() in ['true', 't']

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django_celery_results',
    # 'django_celery_beat',

    'app.apps.AppConfig'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dj_airbnb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
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

WSGI_APPLICATION = 'dj_airbnb.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': "django.contrib.gis.db.backends.postgis",
        "USER": os.getenv("DATABASE_USERNAME", "postgres"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", "airbnb"),
        'NAME': os.getenv("DATABASE_DBNAME", "postgres"),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", 5432),
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    # {
    #     'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    # },
    # # {
    # #     'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    # # },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    # },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    # },
]

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

# USE_I18N = True

# USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'

# CELERY CONFIGURATION

CELERY_CACHE_BACKEND = 'django-cache'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXPIRES = 0

CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5  # from scale 1 to 10 how urgent the task is. 1 is the lowest, 10 the highest

CELERY_DEFAULT_RATE_LIMIT = os.getenv('CELERY_DEFAULT_RATE_LIMIT', '60/m')  # 1 task per 20 seconds  (per worker)
CELERY_TASK_INHERIT_PARENT_PRIORITY = True
timezone = TIME_ZONE
CELERY_WORKER_PREFETCH_MULTIPLIER = os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', 10)

# CELERY BEAT
DJANGO_CELERY_BEAT_TZ_AWARE = USE_TZ
