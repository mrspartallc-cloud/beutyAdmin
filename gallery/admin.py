from django.contrib import admin
from django.utils.html import format_html

from .models import ImagenGaleria


@admin.register(ImagenGaleria)
class ImagenGaleriaAdmin(admin.ModelAdmin):
    list_display = ("preview", "titulo", "destacada", "activa", "orden", "creado")
    list_filter = ("destacada", "activa")
    list_editable = ("destacada", "activa", "orden")
    search_fields = ("titulo", "descripcion")
    ordering = ("orden", "-creado")

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:cover;border-radius:8px;">',
                obj.imagen.url,
            )
        return "—"
