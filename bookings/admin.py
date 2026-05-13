from django.contrib import admin

from .models import Cita, HorarioDisponible, TrabajadoraServicio


class TrabajadoraServicioInline(admin.TabularInline):
    """Edit per-service durations from the Technician admin page."""
    model = TrabajadoraServicio
    extra = 1
    autocomplete_fields = ("servicio",)
    fields = ("servicio", "duracion_minutos", "activo")
    verbose_name = "Service"
    verbose_name_plural = "Services this technician offers"


@admin.register(TrabajadoraServicio)
class TrabajadoraServicioAdmin(admin.ModelAdmin):
    list_display = ("trabajadora", "servicio", "duracion_minutos", "activo")
    list_filter = ("activo", "trabajadora", "servicio")
    list_editable = ("duracion_minutos", "activo")
    search_fields = (
        "trabajadora__nickname", "trabajadora__nombre_completo",
        "servicio__nombre",
    )
    autocomplete_fields = ("trabajadora", "servicio")


@admin.register(HorarioDisponible)
class HorarioDisponibleAdmin(admin.ModelAdmin):
    list_display = ("trabajadora", "dia_semana", "hora_inicio", "hora_fin", "activo")
    list_filter = ("dia_semana", "activo", "trabajadora")
    list_editable = ("activo",)
    autocomplete_fields = ("trabajadora",)


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "hora",
        "duracion_minutos",
        "nombre_cliente",
        "trabajadora",
        "servicio",
        "telefono",
        "estado",
        "creado",
    )
    list_filter = ("estado", "trabajadora", "servicio", "fecha")
    list_editable = ("estado",)
    search_fields = ("nombre_cliente", "telefono", "email", "trabajadora__nickname")
    date_hierarchy = "fecha"
    ordering = ("-fecha", "-hora")
    autocomplete_fields = ("servicio", "trabajadora")
    readonly_fields = ("creado", "actualizado")
    fieldsets = (
        ("Client", {"fields": ("nombre_cliente", "telefono", "email")}),
        ("Appointment", {"fields": ("trabajadora", "servicio", "fecha", "hora",
                                    "duracion_minutos", "estado", "notas")}),
        ("Metadata", {"fields": ("creado", "actualizado"),
                      "classes": ("collapse",)}),
    )
