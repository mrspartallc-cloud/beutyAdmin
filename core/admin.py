from django.contrib import admin

from .models import Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "categoria",
        "precio",
        "duracion_real_display",
        "num_trabajadoras_display",
        "destacado",
        "activo",
        "orden",
    )
    list_filter = ("categoria", "activo", "destacado")
    list_editable = ("precio", "destacado", "activo", "orden")
    search_fields = ("nombre", "descripcion")
    ordering = ("orden", "nombre")
    fieldsets = (
        ("Main Information", {
            "fields": ("nombre", "categoria", "descripcion", "icono"),
        }),
        ("Price", {
            "fields": ("precio",),
        }),
        ("Duration", {
            "fields": ("duracion_minutos",),
            "description": (
                "⚠️ This field does NOT affect appointment scheduling. "
                "Real duration is set per technician in "
                "<a href='/admin/bookings/trabajadoraservicio/'>"
                "Services per Technician</a>. "
                "It's only used as a visual placeholder when no technician "
                "has the service assigned yet."
            ),
        }),
        ("Visibility", {
            "fields": ("destacado", "activo", "orden"),
        }),
    )

    @admin.display(description="Real duration")
    def duracion_real_display(self, obj):
        n = obj.num_trabajadoras_que_lo_hacen
        if n == 0:
            return f"{obj.duracion_minutos} min (placeholder)"
        if n == 1:
            return f"{obj.duracion_real_min} min"
        return f"{obj.duracion_real_min}–{obj.duracion_real_promedio} min"

    @admin.display(description="Technicians")
    def num_trabajadoras_display(self, obj):
        n = obj.num_trabajadoras_que_lo_hacen
        return f"{n} 👥" if n else "⚠ none"
