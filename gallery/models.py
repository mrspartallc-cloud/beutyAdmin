from django.db import models


class ImagenGaleria(models.Model):
    """Photo of a completed work, displayed in the public gallery."""

    titulo = models.CharField(
        "title",
        max_length=120,
        blank=True,
        help_text="Optional. Shown as caption on hover.",
    )
    descripcion = models.CharField(
        "description",
        max_length=255,
        blank=True,
        help_text="Alt text for accessibility and SEO.",
    )
    imagen = models.ImageField(
        "image",
        upload_to="gallery/%Y/%m/",
        help_text="Recommended: 1080×1080 px, max 5MB.",
    )
    destacada = models.BooleanField(
        "featured",
        default=False,
        help_text="Appears larger in the masonry grid.",
    )
    activa = models.BooleanField(
        "active",
        default=True,
        help_text="If unchecked, hidden from the public gallery.",
    )
    orden = models.PositiveIntegerField(
        "display order",
        default=0,
        help_text="Lower number = appears first.",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "-creado"]
        verbose_name = "Gallery Image"
        verbose_name_plural = "Gallery Images"

    def __str__(self):
        return self.titulo or f"Image #{self.pk}"
