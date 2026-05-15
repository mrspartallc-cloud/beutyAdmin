from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from core.views import home
from panel.views import (
    workers_calendar,  # Public read-only
    worker_login,      # ← Worker login
    worker_logout,     # ← Worker logout
    worker_dashboard,  # ← Worker personal dashboard
    worker_complete_appointment,  # ← Complete action
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("reservar/", include(("bookings.urls", "bookings"), namespace="bookings")),
    path("panel/", include("panel.urls")),
    
    # Public workers calendar (no login)
    path("workers/", workers_calendar, name="workers_calendar"),
    
    # Worker portal (with login)
    path("worker/login/", worker_login, name="worker_login"),
    path("worker/logout/", worker_logout, name="worker_logout"),
    path("worker/", worker_dashboard, name="worker_dashboard"),
    path("worker/complete/<int:pk>/", worker_complete_appointment, name="worker_complete_appointment"),
    
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