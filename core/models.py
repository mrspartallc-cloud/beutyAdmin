"""Core models — public-facing services."""
from django.db import models


class Servicio(models.Model):
    """A service offered by the salon (manicure, pedicure, gel, acrylic, etc.)."""

    CATEGORIA_CHOICES = [
        ("manicure", "Manicure"),
        ("pedicure", "Pedicure"),
        ("gel", "Gel"),
        ("acrilico", "Acrylic"),
        ("decoracion", "Nail Art"),
        ("spa", "Hand & Foot Spa"),
        ("otro", "Other"),
    ]

    nombre = models.CharField("name", max_length=100)
    categoria = models.CharField(
        "category", max_length=20, choices=CATEGORIA_CHOICES, default="manicure"
    )
    descripcion = models.TextField(
        "description",
        help_text="Short text shown on the public service card.",
    )
    precio = models.DecimalField(
        "price",
        max_digits=8, decimal_places=2,
        help_text="Price in US dollars.",
    )
    duracion_minutos = models.PositiveIntegerField(
        "reference duration (min)",
        default=60,
        help_text=(
            "Only used as a visual reference on the public landing page. "
            "The REAL duration of each appointment is set per technician "
            "in 'Services per technician'. Leaving 60 works fine."
        ),
    )
    icono = models.CharField(
        "icon",
        max_length=10,
        blank=True,
        default="✨",
        help_text="Decorative emoji or symbol (optional).",
    )
    destacado = models.BooleanField(
        "featured",
        default=False,
        help_text="Highlighted on the landing page.",
    )
    activo = models.BooleanField(
        "active",
        default=True,
        help_text="If unchecked, this service is hidden from the public site.",
    )
    orden = models.PositiveIntegerField(
        "display order",
        default=0,
        help_text="Lower number = appears first.",
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.nombre

    @property
    def duracion_real_min(self):
        """Minimum REAL duration offered by any technician.

        Falls back to `duracion_minutos` if no technician has the service yet.
        This is what's shown to the public — the fastest available option.
        """
        from django.db.models import Min
        from bookings.models import TrabajadoraServicio
        result = TrabajadoraServicio.objects.filter(
            servicio=self, activo=True,
        ).aggregate(min_dur=Min("duracion_minutos"))
        return result["min_dur"] or self.duracion_minutos

    @property
    def duracion_real_promedio(self):
        """Average REAL duration offered by technicians."""
        from django.db.models import Avg
        from bookings.models import TrabajadoraServicio
        result = TrabajadoraServicio.objects.filter(
            servicio=self, activo=True,
        ).aggregate(avg_dur=Avg("duracion_minutos"))
        if result["avg_dur"] is None:
            return self.duracion_minutos
        return int(round(result["avg_dur"]))

    @property
    def num_trabajadoras_que_lo_hacen(self):
        from bookings.models import TrabajadoraServicio
        return TrabajadoraServicio.objects.filter(
            servicio=self, activo=True,
        ).count()
