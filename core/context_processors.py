"""Inyecta los datos del negocio en TODAS las plantillas."""
from django.conf import settings


def site_settings(request):
    return {
        "site": {
            "name": settings.SITE_NAME,
            "tagline": settings.SITE_TAGLINE,
            "phone": settings.SITE_PHONE,
            "whatsapp": settings.SITE_WHATSAPP,
            "email": settings.SITE_EMAIL,
            "address": settings.SITE_ADDRESS,
            "instagram": settings.SITE_INSTAGRAM,
            "horario": settings.SITE_HORARIO,
        }
    }
