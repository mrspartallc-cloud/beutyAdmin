"""
Internal panel models (back-office).

Only superusers/staff access the panel — technicians do NOT have login access.
All management (appointments, availability, income) is handled by the admin.
"""
from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify


# ── US phone validator ───────────────────────────────────────────────────
us_phone_validator = RegexValidator(
    regex=r"^\+?1?[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}$",
    message=(
        "Enter a valid U.S. phone number. "
        "Example: +1 (555) 123-4567 or 555-123-4567."
    ),
)


class Trabajadora(models.Model):
    """
    Salon technician.

    Private (never exposed to the public): nombre_completo, correo, telefono,
    porcentaje. These live only in the back-office.

    Public: nickname, bio, photo. The only thing clients see.
    """

    # ── Private fields (back-office only) ─────────────────────────────
    nombre_completo = models.CharField("full name (private)", max_length=100)
    correo = models.EmailField("email (private)")
    telefono = models.CharField(
        "phone (private)",
        max_length=25,
        validators=[us_phone_validator],
        help_text="U.S. format: +1 (555) 123-4567",
    )
    porcentaje = models.DecimalField(
        "commission (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentage the salon retains from each service.",
    )
    
    # ── Worker Portal Login ───────────────────────────────────────────
    worker_password = models.CharField(
        "worker portal password",
        max_length=100,
        blank=True,
        default="",
        help_text="Password for worker login. Leave blank to disable portal access.",
    )

    # ── Public fields (visible to clients) ────────────────────────────
    nickname = models.SlugField(
        "public nickname",
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text=(
            "Unique public identifier (e.g. 'mara-fit'). If left blank, "
            "it's generated from the name. This is the ONLY thing clients "
            "see — the full name stays private."
        ),
    )
    bio = models.TextField(
        "public bio",
        blank=True,
        max_length=400,
        help_text="Short optional description shown to clients.",
    )
    foto = models.ImageField(
        "photo / avatar",
        upload_to="technicians/",
        null=True,
        blank=True,
        help_text="Optional avatar. Recommended 400×400px square.",
    )

    activa = models.BooleanField("active", default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre_completo"]
        verbose_name = "Technician"
        verbose_name_plural = "Technicians"

    def __str__(self):
        return f"{self.nickname or '(no nickname)'} — {self.nombre_completo}"

    @property
    def display_name(self):
        """The only name shown to the public: the nickname."""
        return self.nickname or f"tech-{self.pk}"

    def save(self, *args, **kwargs):
        # Auto-generate nickname from name if not set
        if not self.nickname:
            base = slugify(self.nombre_completo.split()[0]) if self.nombre_completo else f"tech-{self.pk or 'x'}"
            candidate = base
            n = 2
            while (
                Trabajadora.objects.filter(nickname=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                candidate = f"{base}-{n}"
                n += 1
            self.nickname = candidate
        super().save(*args, **kwargs)





class Registro(models.Model):
    """
    Daily income/commission ledger entry per technician.

    Captures: original amount, salon fee, tip, total received by technician.
    """

    trabajadora = models.ForeignKey(
        Trabajadora,
        on_delete=models.CASCADE,
        related_name="registros",
        verbose_name="technician",
    )
    fecha = models.DateField("date")
    monto_original = models.DecimalField(
        "service price",
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total amount the client paid for the service.",
    )
    monto = models.DecimalField(
        "technician earnings",
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        help_text="Auto-calculated: price minus salon's commission.",
    )
    propina = models.DecimalField(
        "tip",
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        help_text="Tip given by the client (100% goes to the technician).",
    )
    total = models.DecimalField(
        "total received",
        max_digits=10, decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    notas = models.TextField("notes", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado"]
        verbose_name = "Income Record"
        verbose_name_plural = "Income Records"

    def __str__(self):
        return f"{self.trabajadora.display_name} · {self.fecha} · ${self.total}"

    def save(self, *args, **kwargs):
        # Auto-calculate technician's earnings and total
        pct = self.trabajadora.porcentaje if self.trabajadora_id else Decimal("0.00")
        comision = (self.monto_original * pct) / Decimal("100")
        self.monto = self.monto_original - comision
        self.total = self.monto + self.propina
        super().save(*args, **kwargs)
