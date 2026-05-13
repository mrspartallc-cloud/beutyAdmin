"""WSGI entrypoint para servidores como gunicorn / uwsgi."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alambra_nails.settings")
application = get_wsgi_application()
