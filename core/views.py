from django.db.models import Exists, OuterRef
from django.shortcuts import render

from gallery.models import ImagenGaleria
from panel.models import Trabajadora

from .models import Servicio


def home(request):
    """Landing single-page. La reserva ahora vive en /reservar/."""
    workers_destacadas = Trabajadora.objects.filter(activa=True).exclude(
        nickname__isnull=True
    )[:6]

    # Solo mostramos servicios que TIENEN al menos una trabajadora activa
    # asignada (TrabajadoraServicio). Un servicio sin trabajadoras no se
    # puede reservar — lo escondemos para no confundir al cliente.
    from bookings.models import TrabajadoraServicio
    tiene_trabajadora = TrabajadoraServicio.objects.filter(
        servicio=OuterRef("pk"),
        activo=True,
        trabajadora__activa=True,
    )
    servicios = (
        Servicio.objects.filter(activo=True)
        .annotate(_disponible=Exists(tiene_trabajadora))
        .filter(_disponible=True)
    )

    context = {
        "servicios": servicios,
        "galeria": ImagenGaleria.objects.filter(activa=True)[:12],
        "workers_destacadas": workers_destacadas,
    }
    return render(request, "core/home.html", context)
