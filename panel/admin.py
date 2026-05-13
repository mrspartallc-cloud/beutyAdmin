from django.contrib import admin
from django.utils.html import format_html

from bookings.admin import TrabajadoraServicioInline

from .models import Registro, Trabajadora


@admin.register(Trabajadora)
class TrabajadoraAdmin(admin.ModelAdmin):
    inlines = [TrabajadoraServicioInline]
    list_display = (
        "preview",
        "nickname",
        "nombre_completo",
        "telefono",
        "porcentaje",
        "activa",
    )
    list_filter = ("activa",)
    list_editable = ("activa",)
    search_fields = ("nickname", "nombre_completo", "correo", "telefono")
    fieldsets = (
        ("Private (back-office only)", {
            "fields": ("nombre_completo", "correo", "telefono", "porcentaje"),
        }),
        ("Public (visible to clients)", {
            "fields": ("nickname", "bio", "foto"),
        }),
        ("Status", {
            "fields": ("activa",),
        }),
    )

    @admin.display(description="Photo")
    def preview(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="height:40px;width:40px;object-fit:cover;border-radius:50%;">',
                obj.foto.url,
            )
        return "—"


@admin.register(Registro)
class RegistroAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "trabajadora",
        "monto_original",
        "monto",
        "propina",
        "total",
    )
    list_filter = ("trabajadora", "fecha")
    search_fields = ("trabajadora__nickname", "trabajadora__nombre_completo")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)
    readonly_fields = ("monto", "total")
    autocomplete_fields = ("trabajadora",)
