from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "panel"

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="panel/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page=reverse_lazy("panel:login")),
        name="logout",
    ),

    # ── Dashboard ─────────────────────────────────────────────────
    path("", views.dashboard, name="dashboard"),

    # ── Trabajadoras (CRUD + disponibilidad) ─────────────────────
    path("trabajadoras/", views.trabajadoras_list, name="trabajadoras_list"),
    path("trabajadoras/nueva/", views.trabajadora_create, name="trabajadora_create"),
    path("trabajadoras/<int:pk>/editar/", views.trabajadora_update,
         name="trabajadora_update"),
    path("trabajadoras/<int:pk>/eliminar/", views.trabajadora_delete,
         name="trabajadora_delete"),
    path("trabajadoras/<int:pk>/disponibilidad/", views.trabajadora_disponibilidad,
         name="trabajadora_disponibilidad"),

    # ── Servicios por trabajadora (CRUD) ──────────────────────────
    path("trabajadoras/<int:pk>/servicios/", views.trabajadora_servicios,
         name="trabajadora_servicios"),
    path("trabajadoras/<int:pk>/servicios/agregar/",
         views.trabajadora_servicio_add, name="trabajadora_servicio_add"),
    path("trabajadoras/servicio/<int:ts_pk>/editar/",
         views.trabajadora_servicio_edit, name="trabajadora_servicio_edit"),
    path("trabajadoras/servicio/<int:ts_pk>/eliminar/",
         views.trabajadora_servicio_delete, name="trabajadora_servicio_delete"),
    path("trabajadoras/servicio/<int:ts_pk>/toggle/",
         views.trabajadora_servicio_toggle, name="trabajadora_servicio_toggle"),

    # ── Galería (CRUD completo) ───────────────────────────────────
    path("galeria/", views.galeria_list, name="galeria_list"),
    path("galeria/nueva/", views.galeria_create, name="galeria_create"),
    path("galeria/<int:pk>/editar/", views.galeria_update, name="galeria_update"),
    path("galeria/<int:pk>/eliminar/", views.galeria_delete, name="galeria_delete"),
    path("galeria/<int:pk>/toggle/", views.galeria_toggle, name="galeria_toggle"),
    path("galeria/<int:pk>/destacar/", views.galeria_destacar, name="galeria_destacar"),
    path("galeria/<int:pk>/orden/<str:direccion>/", views.galeria_reordenar, name="galeria_reordenar"),

    # ── Servicios (CRUD desde panel) ──────────────────────────────
    path("servicios/", views.servicio_list, name="servicio_list"),
    path("servicios/nuevo/", views.servicio_create, name="servicio_create"),
    path("servicios/<int:pk>/editar/", views.servicio_update, name="servicio_update"),
    path("servicios/<int:pk>/eliminar/", views.servicio_delete, name="servicio_delete"),
    path("servicios/<int:pk>/toggle/", views.servicio_toggle, name="servicio_toggle"),
    path("servicios/<int:pk>/destacar/", views.servicio_destacar, name="servicio_destacar"),

    # Bloques de disponibilidad
    path("disponibilidad/<int:pk>/eliminar/", views.horario_eliminar,
         name="horario_eliminar"),
    path("disponibilidad/<int:pk>/toggle/", views.horario_toggle,
         name="horario_toggle"),

    # ── Citas (gestión global) ───────────────────────────────────
    path("citas/", views.citas_admin, name="citas_admin"),
    path("citas/<int:pk>/aceptar/", views.cita_aceptar, name="cita_aceptar"),
    path("citas/<int:pk>/rechazar/", views.cita_rechazar, name="cita_rechazar"),
    path("citas/<int:pk>/completar/", views.cita_completar, name="cita_completar"),
    path("citas/<int:pk>/asignar/", views.cita_asignar, name="cita_asignar"),
    path("calendario/", views.calendario_admin, name="calendario_admin"),

    # ── Ingresos ─────────────────────────────────────────────────
    path("ingresos/nuevo/", views.ingreso_create, name="ingreso_create"),
    path("ingresos/<int:pk>/editar/", views.ingreso_update, name="ingreso_update"),
    path("ingresos/<int:pk>/eliminar/", views.ingreso_delete, name="ingreso_delete"),

    # ── Resumen financiero ───────────────────────────────────────
    path("resumen/", views.resumen, name="resumen"),

    # ── 🚀 Quick Mode (móvil) ────────────────────────────────────
    path("q/", views.quick_home, name="quick_home"),
    path("q/calendario/", views.quick_calendar, name="quick_calendar"),
    path("q/calendario/<str:fecha>/<str:hora>/", views.quick_day_detail,
         name="quick_day_detail"),
    path("q/nueva/", views.quick_new, name="quick_new"),
    path("q/slots/", views.quick_slots_json, name="quick_slots_json"),
    path("q/<int:pk>/completar/", views.quick_complete, name="quick_complete"),
    path("q/<int:pk>/cancelar/", views.quick_cancel, name="quick_cancel"),
]
