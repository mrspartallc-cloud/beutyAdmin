from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    # Catálogo
    path("", views.select_worker, name="select_worker"),

    # Página de éxito (debe ir ANTES de <slug:nickname>/ por ambigüedad)
    path("exito/<int:pk>/", views.exito, name="exito"),

    # ── Flujo "sin preferencia" (no conoce a nadie) ─────────────
    # Estas rutas DEBEN ir antes de <slug:nickname>/ porque "sin-preferencia"
    # podría confundirse con un nickname válido.
    path("sin-preferencia/", views.cualquiera_detail, name="cualquiera_detail"),
    path("sin-preferencia/disponibilidad/", views.cualquiera_slots,
         name="cualquiera_slots"),
    path("sin-preferencia/<str:fecha>/<str:hora>/", views.cualquiera_confirmar,
         name="cualquiera_confirmar"),

    # ── Flujo por trabajadora (con nickname) ────────────────────
    path("<slug:nickname>/", views.worker_detail, name="worker_detail"),
    path("<slug:nickname>/disponibilidad/", views.slots_disponibles,
         name="slots_disponibles"),
    path("<slug:nickname>/<str:fecha>/<str:hora>/", views.confirmar_cita,
         name="confirmar"),
]
