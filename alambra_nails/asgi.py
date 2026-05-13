"""ASGI entrypoint (uvicorn, daphne, etc.)."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alambra_nails.settings")
application = get_asgi_application()
