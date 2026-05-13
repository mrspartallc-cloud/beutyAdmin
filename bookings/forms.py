"""
Booking flow forms (public and admin).
"""
from datetime import date

from django import forms

from core.models import Servicio
from panel.models import Trabajadora

from .models import Cita, DiaSemana, HorarioDisponible


_TXT = {"class": "form-control"}
_SEL = {"class": "form-control"}


class ConfirmarCitaForm(forms.ModelForm):
    """
    Final step of the public booking flow:
    the client has selected technician + date + time; here they enter their info.
    """

    class Meta:
        model = Cita
        fields = ["nombre_cliente", "telefono", "email", "servicio", "notas"]
        widgets = {
            "nombre_cliente": forms.TextInput(
                attrs={**_TXT, "placeholder": "Your full name",
                       "autocomplete": "name"}
            ),
            "telefono": forms.TextInput(
                attrs={**_TXT, "placeholder": "+1 (555) 123-4567",
                       "autocomplete": "tel", "inputmode": "tel"}
            ),
            "email": forms.EmailInput(
                attrs={**_TXT, "placeholder": "you@example.com (optional)",
                       "autocomplete": "email"}
            ),
            "servicio": forms.Select(attrs={**_SEL}),
            "notas": forms.Textarea(
                attrs={**_TXT, "rows": 3,
                       "placeholder": "Design ideas, allergies, etc."}
            ),
        }
        labels = {
            "nombre_cliente": "Name",
            "telefono": "Phone (US, +1)",
            "email": "Email (optional)",
            "servicio": "Service",
            "notas": "Notes (optional)",
        }

    def __init__(self, *args, trabajadora=None, fecha=None, hora=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter services to the subset the technician offers, if known.
        if trabajadora is not None:
            from .models import TrabajadoraServicio
            servicio_ids = (
                TrabajadoraServicio.objects.filter(
                    trabajadora=trabajadora, activo=True,
                ).values_list("servicio_id", flat=True)
            )
            self.fields["servicio"].queryset = (
                Servicio.objects.filter(activo=True, pk__in=servicio_ids)
            )
        else:
            self.fields["servicio"].queryset = Servicio.objects.filter(activo=True)
        self.fields["servicio"].empty_label = "Select a service"
        self._trabajadora = trabajadora
        self._fecha = fecha
        self._hora = hora

    def clean(self):
        cleaned = super().clean()
        if not (self._trabajadora and self._fecha and self._hora):
            raise forms.ValidationError(
                "Missing appointment information (technician/date/time)."
            )
        instance = Cita(
            **{k: v for k, v in cleaned.items() if v is not None},
            trabajadora=self._trabajadora,
            fecha=self._fecha,
            hora=self._hora,
        )
        try:
            instance.clean()
        except forms.ValidationError as exc:
            for field, msgs in exc.message_dict.items():
                for msg in msgs:
                    self.add_error(field if field in self.fields else None, msg)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.trabajadora = self._trabajadora
        instance.fecha = self._fecha
        instance.hora = self._hora
        if commit:
            instance.save()
        return instance


class HorarioDisponibleForm(forms.ModelForm):
    """Form for adding a weekly availability block."""

    class Meta:
        model = HorarioDisponible
        fields = ["dia_semana", "hora_inicio", "hora_fin", "activo"]
        widgets = {
            "dia_semana": forms.Select(
                attrs={**_SEL}, choices=DiaSemana.choices
            ),
            "hora_inicio": forms.TimeInput(
                attrs={**_TXT, "type": "time", "step": "1800"}
            ),
            "hora_fin": forms.TimeInput(
                attrs={**_TXT, "type": "time", "step": "1800"}
            ),
        }
        labels = {
            "dia_semana": "Day of the week",
            "hora_inicio": "Start time",
            "hora_fin": "End time",
            "activo": "Active",
        }

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("hora_inicio")
        fin = cleaned.get("hora_fin")
        if ini and fin and ini >= fin:
            self.add_error("hora_fin", "End time must be after start time.")
        return cleaned
