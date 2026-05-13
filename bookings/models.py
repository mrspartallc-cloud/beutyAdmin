"""
Booking models — appointments, schedules, and per-technician services.
"""
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


# ── US phone validator ──────────────────────────────────────────────────
us_phone_validator = RegexValidator(
    regex=r"^\+?1?[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}$",
    message=(
        "Enter a valid U.S. phone number. "
        "Example: +1 (555) 123-4567 or 555-123-4567."
    ),
)


# ── Slot configuration ──────────────────────────────────────────────────
SLOT_MINUTES = 60  # legacy fallback; service layer uses STEP_MINUTES=15
VENTANA_RESERVA_DIAS = 60


class DiaSemana(models.IntegerChoices):
    LUN = 0, "Monday"
    MAR = 1, "Tuesday"
    MIE = 2, "Wednesday"
    JUE = 3, "Thursday"
    VIE = 4, "Friday"
    SAB = 5, "Saturday"
    DOM = 6, "Sunday"


class HorarioDisponible(models.Model):
    """A recurring weekly availability block for a technician.

    Example: "Monday 9:00 AM – 1:00 PM".
    """

    trabajadora = models.ForeignKey(
        "panel.Trabajadora",
        on_delete=models.CASCADE,
        related_name="horarios_disponibles",
        verbose_name="technician",
    )
    dia_semana = models.IntegerField("day of week", choices=DiaSemana.choices)
    hora_inicio = models.TimeField("start time")
    hora_fin = models.TimeField("end time")
    activo = models.BooleanField("active", default=True)

    class Meta:
        ordering = ["trabajadora", "dia_semana", "hora_inicio"]
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hora_fin__gt=models.F("hora_inicio")),
                name="hora_fin_after_hora_inicio",
                violation_error_message="End time must be after start time.",
            ),
        ]

    def __str__(self):
        return (
            f"{self.trabajadora.display_name} · "
            f"{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"
        )

    def generar_slots(self):
        """List of possible times within this block, spaced by SLOT_MINUTES."""
        slots = []
        cursor = datetime.combine(date.today(), self.hora_inicio)
        fin = datetime.combine(date.today(), self.hora_fin)
        delta = timedelta(minutes=SLOT_MINUTES)
        while cursor + delta <= fin + timedelta(seconds=1):
            slots.append(cursor.time().replace(second=0, microsecond=0))
            cursor += delta
        return slots


class TrabajadoraServicio(models.Model):
    """Technician ↔ service mapping with custom duration.

    Each technician offers a subset of services, each with its own time:
        Maria — Manicure — 60 min
        Antonia — Manicure — 35 min
        Maria — Pedicure — 90 min
    """

    trabajadora = models.ForeignKey(
        "panel.Trabajadora",
        on_delete=models.CASCADE,
        related_name="servicios_que_realiza",
        verbose_name="technician",
    )
    servicio = models.ForeignKey(
        "core.Servicio",
        on_delete=models.CASCADE,
        related_name="trabajadoras_que_lo_realizan",
        verbose_name="service",
    )
    duracion_minutos = models.PositiveIntegerField(
        "duration (minutes)",
        validators=[MinValueValidator(5)],
        help_text=(
            "Time THIS technician takes for THIS service. "
            "Overrides the service's reference duration."
        ),
    )
    activo = models.BooleanField(
        "active",
        default=True,
        help_text="Uncheck if the technician temporarily stops offering this service.",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["trabajadora", "servicio"]
        verbose_name = "Service per Technician"
        verbose_name_plural = "Services per Technician"
        constraints = [
            models.UniqueConstraint(
                fields=["trabajadora", "servicio"],
                name="unique_trabajadora_servicio",
                violation_error_message="This technician already has that service assigned.",
            ),
        ]

    def __str__(self):
        return (
            f"{self.trabajadora.display_name} · {self.servicio.nombre} · "
            f"{self.duracion_minutos} min"
        )


class Cita(models.Model):
    """Appointment booked by a client with a specific technician."""

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_COMPLETADA = "completada"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pending"),
        (ESTADO_CONFIRMADA, "Confirmed"),
        (ESTADO_COMPLETADA, "Completed"),
        (ESTADO_CANCELADA, "Cancelled"),
    ]

    nombre_cliente = models.CharField("client name", max_length=120)
    telefono = models.CharField(
        "phone",
        max_length=25, validators=[us_phone_validator],
        blank=True, default="",
    )
    email = models.EmailField("email", blank=True)
    servicio = models.ForeignKey(
        "core.Servicio",
        on_delete=models.PROTECT,
        related_name="citas",
        verbose_name="service",
    )
    trabajadora = models.ForeignKey(
        "panel.Trabajadora",
        on_delete=models.PROTECT,
        related_name="citas",
        null=True, blank=True,
        verbose_name="technician",
        help_text="If empty, an admin will assign a technician later.",
    )
    fecha = models.DateField("date")
    hora = models.TimeField("time")
    duracion_minutos = models.PositiveIntegerField(
        "duration (minutes)",
        default=60,
        help_text=(
            "Auto-filled from the (technician, service) pair on save. "
            "Editable manually if the admin needs to adjust."
        ),
    )
    notas = models.TextField("notes", blank=True)
    estado = models.CharField(
        "status",
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE,
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-hora"]
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"
        indexes = [
            models.Index(fields=["fecha", "hora"]),
            models.Index(fields=["trabajadora", "fecha"]),
            models.Index(fields=["fecha", "estado"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        worker = self.trabajadora.display_name if self.trabajadora else "(unassigned)"
        return f"{self.nombre_cliente} → {worker} · {self.fecha} {self.hora:%H:%M}"

    @property
    def hora_fin(self):
        if not self.hora:
            return None
        inicio = datetime.combine(self.fecha or date.today(), self.hora)
        fin = inicio + timedelta(minutes=self.duracion_minutos or 60)
        return fin.time()

    @property
    def rango_minutos(self):
        if not self.hora:
            return (0, 0)
        ini = self.hora.hour * 60 + self.hora.minute
        return (ini, ini + (self.duracion_minutos or 60))

    def _autorelenar_duracion(self):
        """If no explicit duration, look it up in TrabajadoraServicio."""
        if not (self.trabajadora_id and self.servicio_id):
            return
        ts = TrabajadoraServicio.objects.filter(
            trabajadora_id=self.trabajadora_id,
            servicio_id=self.servicio_id,
            activo=True,
        ).first()
        if ts:
            self.duracion_minutos = ts.duracion_minutos
        elif not self.duracion_minutos:
            from core.models import Servicio
            try:
                s = Servicio.objects.get(pk=self.servicio_id)
                self.duracion_minutos = s.duracion_minutos or 60
            except Servicio.DoesNotExist:
                self.duracion_minutos = 60

    def save(self, *args, **kwargs):
        # Auto-rellenar duración
        self._autorelenar_duracion()
        # CRÍTICO: Ejecutar validaciones antes de guardar
        # Esto previene que se guarden citas con fechas pasadas
        self.full_clean()
        super().save(*args, **kwargs)
 

    def clean(self):
        super().clean()
        errors = {}

        if self.fecha and self.fecha < date.today():
            errors["fecha"] = "Cannot book appointments in the past."

        if self.fecha and self.fecha > date.today() + timedelta(days=VENTANA_RESERVA_DIAS):
            errors["fecha"] = (
                f"We only accept bookings up to {VENTANA_RESERVA_DIAS} days in advance."
            )

        if self.trabajadora_id and self.servicio_id and not self.duracion_minutos:
            self._autorelenar_duracion()

        # Range overlap with same technician
        if (
            self.trabajadora_id
            and self.fecha
            and self.hora
            and self.estado != self.ESTADO_CANCELADA
        ):
            ini, fin = self.rango_minutos
            qs = Cita.objects.filter(
                trabajadora_id=self.trabajadora_id,
                fecha=self.fecha,
            ).exclude(estado=self.ESTADO_CANCELADA)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            for otra in qs:
                o_ini, o_fin = otra.rango_minutos
                if ini < o_fin and o_ini < fin:
                    errors["hora"] = (
                        f"@{self.trabajadora.nickname} already has an appointment "
                        f"from {otra.hora:%H:%M}–{otra.hora_fin:%H:%M}. "
                        "Please choose a different time."
                    )
                    break

        # Slot must fall inside an active availability block
        if self.trabajadora_id and self.fecha and self.hora:
            tiene_horarios = HorarioDisponible.objects.filter(
                trabajadora_id=self.trabajadora_id, activo=True,
            ).exists()
            if tiene_horarios:
                dia = self.fecha.weekday()
                _, fin_min = self.rango_minutos
                fin_h = fin_min // 60
                fin_m = fin_min % 60
                fin_time = time(fin_h % 24, fin_m)
                bloque = HorarioDisponible.objects.filter(
                    trabajadora_id=self.trabajadora_id,
                    dia_semana=dia,
                    activo=True,
                    hora_inicio__lte=self.hora,
                    hora_fin__gte=fin_time,
                )
                if not bloque.exists():
                    errors["hora"] = (
                        "The technician is not available at that time "
                        "(or the appointment exceeds their working block)."
                    )

        if errors:
            raise ValidationError(errors)
