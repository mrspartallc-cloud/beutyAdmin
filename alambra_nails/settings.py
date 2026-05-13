"""
Settings de Alambra Nails.

Lee variables sensibles desde el entorno. Para desarrollo local basta con
copiar .env.example a .env (o exportarlas a mano) y ejecutar el servidor.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Cargar archivo .env si existe (en la raíz del proyecto) ──────────
# Esto permite que las variables del .env entren a os.environ ANTES de
# que las leamos abajo. Si no hay python-dotenv instalado, el proyecto
# sigue funcionando — solo no leerá automáticamente el .env.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("1", "true", "yes", "on")


# --- Seguridad ---------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-CAMBIA-ESTA-CLAVE-EN-PRODUCCION-1234567890",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,*"
).split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# Cabeceras de seguridad (activas en producción).
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 días
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --- Apps --------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Apps locales
    "core.apps.CoreConfig",
    "gallery.apps.GalleryConfig",
    "bookings.apps.BookingsConfig",
    "panel.apps.PanelConfig",
]

# Auth: redirige al login del panel cuando se intenta acceder a una vista protegida.
LOGIN_URL = "/panel/login/"
LOGIN_REDIRECT_URL = "/panel/"
LOGOUT_REDIRECT_URL = "/panel/login/"
LOGOUT_REDIRECT_URL = "/panel/login/"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve estáticos en prod
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "alambra_nails.urls"

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
                "core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "alambra_nails.wsgi.application"


# --- Base de datos -----------------------------------------------------------
# SQLite para desarrollo. En producción usa PostgreSQL configurando DATABASE_URL
# o ajustando las variables. Si quieres dj-database-url, agrégalo a requirements.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

if os.environ.get("POSTGRES_DB"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }


# --- Validación de contraseñas ----------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internacionalización ---------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIMEZONE", "America/New_York")
USE_I18N = True
USE_TZ = True


# --- Estáticos y media ------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise comprime y cachea estáticos en producción.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Tamaño máximo de uploads (5MB).
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Datos del negocio (editables sin tocar código) -------------------------
SITE_NAME = "Alambra Nails"
SITE_TAGLINE = "Designs that captivate, hands that tell stories"
SITE_PHONE = os.environ.get("SITE_PHONE", "+1 (555) 555-5555")
SITE_WHATSAPP = os.environ.get("SITE_WHATSAPP", "4074898135")  # digits only, US
SITE_EMAIL = os.environ.get("SITE_EMAIL", "hello@alambranails.com")
SITE_ADDRESS = os.environ.get("SITE_ADDRESS", "123 Beauty Cerca de la Mata de Mangos")
SITE_INSTAGRAM = os.environ.get("SITE_INSTAGRAM", "alambra.nails")
SITE_HORARIO = os.environ.get("SITE_HORARIO", "Mon–Sat · 9:00 AM — 7:00 PM")
