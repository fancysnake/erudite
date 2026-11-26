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
    LANGUAGE_CODE=(str, "en"),
    MEDIA_ROOT=(str, "media"),
    SECRET_KEY=str,
    STATIC_ROOT=(str, "staticfiles"),
    TIME_ZONE=(str, "Europe/Warsaw"),
)

# env() lets an empty value through; it would fail far from here, or not at all.
for _required in ("SECRET_KEY", "DATABASE_URL"):
    if not env(_required):
        _missing = f"Set the {_required} environment variable"
        raise ImproperlyConfigured(_missing)

DEBUG: bool = env("DEBUG")
# The template coverage plugin needs it on under test.
TEMPLATE_DEBUG: bool = env("TEMPLATE_DEBUG", default=DEBUG)
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
    "erudite.gates.cli.django.apps.CliGatesConfig",
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
# Commands build their services from this path; gates never import inits.
SERVICES_FACTORY = "erudite.inits.Services"

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
            "debug": TEMPLATE_DEBUG,
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
# Files of other projects, downloaded by `mise run dj downloadvendor`. Outside
# `src`, so the linters do not read them.
VENDOR_STATIC_DIR = BASE_DIR.parent.parent / "vendor"
# `sha384` is the base64 form an SRI attribute takes.
VENDOR_DEPENDENCIES: list[dict[str, str]] = [
    {
        "name": "htmx",
        "url": "https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js",
        "filename": "htmx.min.js",
        "sha384": "/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz",
    }
]
STATICFILES_DIRS = [BASE_DIR / "static", ("vendor", VENDOR_STATIC_DIR)]

# Cover images of books.
MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

UNFOLD = {"SITE_TITLE": "erudite", "SITE_HEADER": "erudite", "SITE_SYMBOL": "book_2"}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
