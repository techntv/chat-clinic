"""The one settings module. Every value comes from the environment (or `.env`)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

# --- Django core -----------------------------------------------------------------------------
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "clinic",
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
WSGI_APPLICATION = "config.wsgi.application"

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
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://clinic:clinic@localhost:5432/clinic")
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
}

# --- Messenger / Meta ------------------------------------------------------------------------
FB_VERIFY_TOKEN = env.str("FB_VERIFY_TOKEN", default="")
FB_APP_SECRET = env.str("FB_APP_SECRET", default="")
GRAPH_API_VERSION = env.str("GRAPH_API_VERSION", default="v24.0")
GRAPH_API_TIMEOUT_SECONDS = env.float("GRAPH_API_TIMEOUT_SECONDS", default=10.0)

# --- Claude ----------------------------------------------------------------------------------
# ANTHROPIC_API_KEY is read directly by the anthropic SDK.
CLAUDE_MODEL = env.str("CLAUDE_MODEL", default="claude-haiku-5-5")
CLAUDE_EFFORT = env.str("CLAUDE_EFFORT", default="low")
CLAUDE_MAX_TOKENS = env.int("CLAUDE_MAX_TOKENS", default=2048)
CLAUDE_MAX_TOOL_ROUNDS = env.int("CLAUDE_MAX_TOOL_ROUNDS", default=4)
CLAUDE_HISTORY_MESSAGES = env.int("CLAUDE_HISTORY_MESSAGES", default=12)
CLAUDE_TIMEOUT_SECONDS = env.float("CLAUDE_TIMEOUT_SECONDS", default=60.0)
# USD per million tokens, used only for cost logging / the eval script.
CLAUDE_INPUT_USD_PER_MTOK = env.float("CLAUDE_INPUT_USD_PER_MTOK", default=0.10)
CLAUDE_OUTPUT_USD_PER_MTOK = env.float("CLAUDE_OUTPUT_USD_PER_MTOK", default=0.50)

# --- Google Sheets ---------------------------------------------------------------------------
GOOGLE_SERVICE_ACCOUNT_FILE = env.str("GOOGLE_SERVICE_ACCOUNT_FILE", default="")
SHEET_CACHE_MINUTES = env.int("SHEET_CACHE_MINUTES", default=15)

# --- Background processing -------------------------------------------------------------------
BACKGROUND_WORKERS = env.int("BACKGROUND_WORKERS", default=4)
# Tests flip this to True so webhook work runs inline.
BACKGROUND_SYNC = env.bool("BACKGROUND_SYNC", default=False)
