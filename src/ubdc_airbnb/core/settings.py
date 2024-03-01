import os
import warnings
from pathlib import Path

from ubdc_airbnb.airbnb_interface.airbnb_api import AirbnbApi

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "!@%ff)awnl(dx)6!!$zrdd9=l_6b76vl+*pw2jj54vljjiz2-y"

# APP SETTINGS
AIRBNB_APP_VERSION = os.getenv("APP_VERSION", "-")
AIRBNB_API_ENDPOINT = os.getenv("AIRBNB_API_ENDPOINT", "https://www.airbnb.co.uk/api")
AIRBNB_PUBLIC_API_KEY = os.getenv("AIRBNB_PUBLIC_API_KEY", "d306zoyjsyarp7ifhu67rjxn52tv0t20")
AIRBNB_LISTINGS_MOVED_MIN_DISTANCE = os.getenv("AIRBNB_LISTINGS_MOVED_MIN_DISTANCE", 150)
AIRBNB_PROXY = "http://8e8eaee704534e969276679126b188ba:@proxy.crawlera.com:8011"
if AIRBNB_PROXY is None:
    message = f"No proxy is set. Not using a proxy could lead Airbnb QoS to be activated."
    warnings.warn(message)

EXTRA_HEADERS = {x.replace("_", "-"): os.environ[x] for x in os.environ if x.startswith("PROXY_HEADER_")}
AIRBNB_CLIENT = AirbnbApi(
    proxy=AIRBNB_PROXY,
    extra_headers=EXTRA_HEADERS,
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_ENV") == "DEV"
ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    "ubdc_airbnb",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django_celery_results",
    "django_celery_beat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ubdc_airbnb.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "USER": os.getenv("DATABASE_USERNAME", "postgres"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", "postgres"),
        "NAME": os.getenv("DATABASE_DBNAME", "postgres"),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", 5432),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "/static/"

# CELERY CONFIGURATION
CACHE_BACKEND = "django-cache"
RESULT_BACKEND = "django-db"
# CELERY_RESULT_EXPIRES = 1 * 60 * 60 * 24 * 7  # 7 days
CELERY_RESULT_EXPIRES = 0  # Never expire
CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5  # 1 is the lowest, 10 the highest
CELERY_TASK_INHERIT_PARENT_PRIORITY = True
TIMEZONE = TIME_ZONE
CELERY_WORKER_PREFETCH_MULTIPLIER = os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", 10)

CELERY_BROKER_URI = (
    "pyamqp://{rabbit_username}:{rabbit_password}@{rabbit_host}:{rabbit_port}/{rabbit_virtual_host}".format(
        rabbit_username=os.getenv("RABBITMQ_USERNAME", "rabbit"),
        rabbit_password=os.getenv("RABBITMQ_PASSWORD", "carrot"),
        rabbit_host=os.getenv("RABBITMQ_HOST", "localhost"),
        rabbit_port=os.getenv("RABBITMQ_PORT", 5672),
        rabbit_virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
    )
)

# CELERY BEAT
DJANGO_CELERY_BEAT_TZ_AWARE = USE_TZ
