import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "validator.apps.ValidatorConfig",
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
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Local-memory cache is suitable for the interview MVP. Use Redis in production.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "business-email-validation",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["validator.authentication.APIKeyAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": os.getenv("API_RATE_LIMIT", "30/min")},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Business Email Validation API",
    "DESCRIPTION": (
        "Best-effort email deliverability estimation. "
        "Results do not guarantee that a mailbox exists."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENTS": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            }
        }
    },
    "SECURITY": [{"ApiKeyAuth": []}],
}

API_KEY = os.getenv("API_KEY", "replace-this-api-key")
SMTP_CHECKS_ENABLED = os.getenv("SMTP_CHECKS_ENABLED", "False").lower() == "true"
GLOBAL_SMTP_ENABLED = os.getenv("GLOBAL_SMTP_ENABLED", "True").lower() == "true"
SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "4"))
DNS_TIMEOUT_SECONDS = float(os.getenv("DNS_TIMEOUT_SECONDS", "3"))
DNS_LIFETIME_SECONDS = float(os.getenv("DNS_LIFETIME_SECONDS", "4"))
SMTP_GLOBAL_CONCURRENCY_LIMIT = int(os.getenv("SMTP_GLOBAL_CONCURRENCY_LIMIT", "5"))
SMTP_DOMAIN_CONCURRENCY_LIMIT = int(os.getenv("SMTP_DOMAIN_CONCURRENCY_LIMIT", "1"))
SMTP_HELO_NAME = os.getenv("SMTP_HELO_NAME", "email-validator.example.invalid")
CACHE_TTL_TRUE = int(os.getenv("CACHE_TTL_TRUE", "900"))
CACHE_TTL_FALSE = int(os.getenv("CACHE_TTL_FALSE", "3600"))
CACHE_TTL_UNKNOWN = int(os.getenv("CACHE_TTL_UNKNOWN", "60"))
