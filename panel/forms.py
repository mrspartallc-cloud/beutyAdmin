"""Forms for the internal panel (back-office)."""
from decimal import Decimal

from django import forms

from .models import Registro, Trabajadora


_TXT = {"class": "form-control"}
_NUM = {"class": "form-control", "step": "0.01", "min": "0"}


class TrabajadoraForm(forms.ModelForm):
    class Meta:
        model = Trabajadora
        fields = [
            "nombre_completo",
            "nickname",
            "correo",
            "telefono",
            "porcentaje",
            "bio",
            "foto",
            "activa",
        ]
        widgets = {
            "nombre_completo": forms.TextInput(
                attrs={**_TXT, "placeholder": "e.g. Andrea Martinez (private)"}
            ),
            "nickname": forms.TextInput(
                attrs={**_TXT, "placeholder": "auto-generated if empty"}
            ),
            "correo": forms.EmailInput(
                attrs={**_TXT, "placeholder": "andrea@example.com"}
            ),
            "telefono": forms.TextInput(
                attrs={**_TXT, "placeholder": "+1 (555) 123-4567"}
            ),
            "porcentaje": forms.NumberInput(
                attrs={**_NUM, "max": "100"}
            ),
            "bio": forms.Textarea(
                attrs={**_TXT, "rows": 3,
                       "placeholder": "Short description shown to clients"}
            ),
            "foto": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }
        labels = {
            "nombre_completo": "Full name (private)",
            "nickname": "Public nickname",
            "correo": "Email (private)",
            "telefono": "Phone (private)",
            "porcentaje": "Salon commission (%)",
            "bio": "Public bio",
            "foto": "Photo / avatar",
            "activa": "Active",
        }


class RegistroForm(forms.ModelForm):
    class Meta:
        model = Registro
        fields = ["trabajadora", "fecha", "monto_original", "propina", "notas"]
        widgets = {
            "trabajadora": forms.Select(attrs=_TXT),
            "fecha": forms.DateInput(
                attrs={**_TXT, "type": "date"}
            ),
            "monto_original": forms.NumberInput(
                attrs={**_NUM, "placeholder": "0.00"}
            ),
            "propina": forms.NumberInput(
                attrs={**_NUM, "placeholder": "0.00"}
            ),
            "notas": forms.Textarea(
                attrs={**_TXT, "rows": 2, "placeholder": "Optional notes"}
            ),
        }
        labels = {
            "trabajadora": "Technician",
            "fecha": "Date",
            "monto_original": "Service price ($)",
            "propina": "Tip ($)",
            "notas": "Notes",
        }


# ── Gallery form ────────────────────────────────────────────────────────
class ImagenGaleriaForm(forms.ModelForm):
    """Create/edit gallery images from the panel."""
    class Meta:
        from gallery.models import ImagenGaleria
        model = ImagenGaleria
        fields = ["titulo", "descripcion", "imagen", "destacada", "activa", "orden"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={**_TXT, "placeholder": "e.g. French acrylics — by Andrea"},
            ),
            "descripcion": forms.TextInput(
                attrs={**_TXT, "placeholder": "Short description for accessibility"},
            ),
            "imagen": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"},
            ),
            "orden": forms.NumberInput(
                attrs={**_NUM, "min": "0", "step": "1"},
            ),
        }
        labels = {
            "titulo": "Title (optional)",
            "descripcion": "Description (optional, for SEO)",
            "imagen": "Image",
            "destacada": "Featured (larger in the grid)",
            "activa": "Active (visible on public site)",
            "orden": "Display order (lower = first)",
        }


# ── Service form ────────────────────────────────────────────────────────
class ServicioForm(forms.ModelForm):
    """Create/edit services from the panel."""
    class Meta:
        from core.models import Servicio
        model = Servicio
        fields = ["nombre", "categoria", "descripcion", "precio",
                  "duracion_minutos", "icono", "destacado", "activo", "orden"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={**_TXT, "placeholder": "e.g. Classic Manicure"},
            ),
            "categoria": forms.Select(attrs=_TXT),
            "descripcion": forms.Textarea(
                attrs={**_TXT, "rows": 3,
                       "placeholder": "Short description shown on the public card."},
            ),
            "precio": forms.NumberInput(
                attrs={**_NUM, "placeholder": "0.00"},
            ),
            "duracion_minutos": forms.NumberInput(
                attrs={**_NUM, "min": "5", "step": "5"},
            ),
            "icono": forms.TextInput(
                attrs={**_TXT, "maxlength": "4", "placeholder": "✨"},
            ),
            "orden": forms.NumberInput(
                attrs={**_NUM, "min": "0", "step": "1"},
            ),
        }
