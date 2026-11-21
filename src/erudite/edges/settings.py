"""Django settings, read from the environment."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# src/erudite
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    ALLOWED_HOSTS=(list, ["localhost"]),
    DATABASE_URL=str,
    DEBUG=(bool, False),
    ENV=(str, "development"),
    LANGUAGE_CODE=(str, "en"),
    SECRET_KEY=str,
    STATIC_ROOT=(str, "staticfiles"),
    TIME_ZONE=(str, "Europe/Warsaw"),
)

# env() lets an empty value through; it would fail far from here, or not at all.
for _required in ("SECRET_KEY", "DATABASE_URL"):
    if not env(_required):
        _missing = f"Set the {_required} environment variable"
        raise ImproperlyConfigured(_missing)

ENV = env("ENV")
DEBUG: bool = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS: list[str] = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "erudite.links.db.django.apps.DbConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "erudite.inits.ServiceInjectionMiddleware",
]

ROOT_URLCONF = "erudite.gates.web.django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            # The template coverage plugin needs debug on under test.
            "debug": DEBUG or ENV == "test",
        },
    }
]

WSGI_APPLICATION = "erudite.edges.wsgi.application"

DATABASES = {"default": {**env.db("DATABASE_URL"), "ATOMIC_REQUESTS": True}}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("LANGUAGE_CODE")
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT")
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

UNFOLD = {"SITE_TITLE": "erudite", "SITE_HEADER": "erudite", "SITE_SYMBOL": "book_2"}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
