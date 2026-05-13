from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from core.views import home
from panel.views import workers_calendar  # ← Agregar import

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("reservar/", include(("bookings.urls", "bookings"), namespace="bookings")),
    path("panel/", include("panel.urls")),
    path("workers/", workers_calendar, name="workers_calendar"),  # ← Nueva ruta
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin branding
admin.site.site_header = "Alambra Nails · Admin"
admin.site.site_title = "Alambra Nails"
admin.site.index_title = "Salon Management"