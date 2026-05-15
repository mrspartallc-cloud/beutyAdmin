"""Django admin configuration for panel models."""
from django.contrib import admin
from .models import Trabajadora, Registro


@admin.register(Trabajadora)
class TrabajadoraAdmin(admin.ModelAdmin):
    """Admin interface for salon technicians."""
    
    list_display = [
        "nickname",
        "nombre_completo",
        "correo",
        "telefono",
        "porcentaje",
        "has_portal_access",
        "activa",
    ]
    
    list_filter = ["activa"]
    
    search_fields = [
        "nickname",
        "nombre_completo",
        "correo",
        "telefono",
    ]
    
    readonly_fields = ["creado", "actualizado"]
    
    fieldsets = (
        ("Private Information (Back-office Only)", {
            "fields": (
                "nombre_completo",
                "correo",
                "telefono",
                "porcentaje",
            ),
            "description": "This information is NEVER shown to clients."
        }),
        
        ("Worker Portal Login", {
            "fields": ("worker_password",),
            "description": (
                "Set a password to grant this worker access to the worker portal "
                "at /worker/login/. Workers login with their nickname + this password. "
                "Leave blank to disable portal access."
            ),
        }),
        
        ("Public Information (Client-facing)", {
            "fields": (
                "nickname",
                "bio",
                "foto",
            ),
            "description": "Only the nickname and photo are shown to clients."
        }),
        
        ("Status & Metadata", {
            "fields": (
                "activa",
                "creado",
                "actualizado",
            ),
            "classes": ("collapse",),
        }),
    )
    
    def has_portal_access(self, obj):
        """Show if worker has portal password set."""
        return bool(obj.worker_password)
    has_portal_access.boolean = True
    has_portal_access.short_description = "Portal Access"


@admin.register(Registro)
class RegistroAdmin(admin.ModelAdmin):
    """Admin interface for income records."""
    
    list_display = [
        "trabajadora",
        "fecha",
        "monto_original",
        "monto",
        "propina",
        "total",
    ]
    
    list_filter = [
        "trabajadora",
        "fecha",
    ]
    
    search_fields = [
        "trabajadora__nickname",
        "trabajadora__nombre_completo",
        "notas",
    ]
    
    date_hierarchy = "fecha"
    
    readonly_fields = ["monto", "total", "creado"]
    
    fieldsets = (
        (None, {
            "fields": (
                "trabajadora",
                "fecha",
                "monto_original",
                "propina",
                "notas",
            )
        }),
        
        ("Auto-calculated (Read-only)", {
            "fields": ("monto", "total"),
            "classes": ("collapse",),
            "description": (
                "These values are automatically calculated based on "
                "the technician's commission percentage."
            ),
        }),
        
        ("Metadata", {
            "fields": ("creado",),
            "classes": ("collapse",),
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("trabajadora")