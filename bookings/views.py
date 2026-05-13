"""
Flujo público de reservas - CORREGIDO con validación REFORZADA de fechas Y horas pasadas.
"""
from datetime import date as _date, datetime, time, timedelta
import logging

from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from core.models import Servicio
from panel.models import Trabajadora

from .forms import ConfirmarCitaForm
from .models import Cita, HorarioDisponible, SLOT_MINUTES, VENTANA_RESERVA_DIAS

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────
def _slots_disponibles(trabajadora, fecha):
    """Slots libres de UNA trabajadora en una fecha dada."""
    if fecha < _date.today():
        return []
    dia = fecha.weekday()
    bloques = HorarioDisponible.objects.filter(
        trabajadora=trabajadora, dia_semana=dia, activo=True
    )
    todos = []
    for b in bloques:
        todos.extend(b.generar_slots())

    ocupados = set(
        Cita.objects.filter(trabajadora=trabajadora, fecha=fecha)
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .values_list("hora", flat=True)
    )

    # ✅ FILTRADO AUTOMÁTICO: Si es hoy, excluir horas pasadas
    ahora = datetime.now().time() if fecha == _date.today() else time.min
    return [s for s in todos if s not in ocupados and s > ahora]


def _slots_agregados(fecha):
    """Para el flujo 'sin preferencia':
    devuelve un dict {slot: [trabajadoras_libres]} con los slots donde
    al menos una trabajadora activa está libre.
    """
    if fecha < _date.today():
        return {}
    workers = Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True)
    agregado = {}
    for w in workers:
        for s in _slots_disponibles(w, fecha):
            agregado.setdefault(s, []).append(w)
    return agregado


def _dias_con_horario_global():
    """Días de la semana donde HAY al menos un bloque activo en todo el spa."""
    return list(
        HorarioDisponible.objects.filter(activo=True, trabajadora__activa=True)
        .values_list("dia_semana", flat=True)
        .distinct()
    )


def _elegir_trabajadora_libre(fecha, hora):
    """Para 'sin preferencia': escoge la trabajadora con menos citas ese día.
    Devuelve None si nadie está libre en ese slot.
    """
    candidatas = _slots_agregados(fecha).get(hora, [])
    if not candidatas:
        return None
    # Ordenar por carga (citas activas) ese día — la menos saturada primero.
    candidatas.sort(
        key=lambda w: Cita.objects.filter(
            trabajadora=w, fecha=fecha
        ).exclude(estado=Cita.ESTADO_CANCELADA).count()
    )
    return candidatas[0]


def _validar_fecha_hora_futura(fecha, hora):
    """
    Valida que la fecha y hora sean futuras.
    Retorna (es_valido: bool, mensaje_error: str)
    
    IMPORTANTE: Esta función debe ejecutarse SIEMPRE antes de guardar una cita.
    """
    hoy = _date.today()
    ahora = datetime.now()
    
    # Log para debugging
    fecha_hora_cita = datetime.combine(fecha, hora)
    logger.warning(f"🔍 Validando cita: {fecha_hora_cita} | Ahora: {ahora}")
    
    # Validar fecha pasada
    if fecha < hoy:
        logger.warning(f"❌ RECHAZADA: Fecha pasada {fecha} < {hoy}")
        return False, "Cannot book appointments in the past. Please select a future date."
    
    # Si es HOY, validar que la hora no haya pasado
    if fecha == hoy:
        # Combinar fecha y hora para comparar con el momento actual
        if fecha_hora_cita <= ahora:
            logger.warning(f"❌ RECHAZADA: Hora pasada {fecha_hora_cita} <= {ahora}")
            return False, "Cannot book appointments for past times. Please select a future time."
    
    logger.info(f"✅ APROBADA: Cita futura {fecha_hora_cita}")
    return True, ""


# ─────────────────────────────────────────────────────────────────────────
# A. CATÁLOGO + FLUJO POR TRABAJADORA
# ─────────────────────────────────────────────────────────────────────────
@require_GET
def select_worker(request):
    """Catálogo público de trabajadoras + opción 'sin preferencia'."""
    q = (request.GET.get("q") or "").strip()
    workers = Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True)
    if q:
        workers = workers.filter(nickname__icontains=q)
    return render(
        request,
        "bookings/select_worker.html",
        {"workers": workers, "q": q},
    )


@require_GET
def worker_detail(request, nickname):
    worker = get_object_or_404(Trabajadora, nickname=nickname, activa=True)

    # Servicios que ESTA trabajadora ofrece (con duración personalizada).
    from .models import TrabajadoraServicio
    servicios_que_hace = list(
        TrabajadoraServicio.objects.filter(
            trabajadora=worker, activo=True,
        )
        .select_related("servicio")
        .order_by("servicio__orden", "servicio__nombre")
    )

    dias_con_horario = list(
        worker.horarios_disponibles.filter(activo=True)
        .values_list("dia_semana", flat=True)
        .distinct()
    )

    return render(
        request,
        "bookings/worker_detail.html",
        {
            "worker": worker,
            "servicios_que_hace": servicios_que_hace,
            "dias_con_horario": dias_con_horario,
            "ventana_dias": VENTANA_RESERVA_DIAS,
            "hoy": _date.today(),
        },
    )


@require_GET
def slots_disponibles(request, nickname):
    """Endpoint AJAX: ?fecha=YYYY-MM-DD&servicio=ID
    Si viene servicio, usa la capa de servicios (respeta duración real).
    Si NO viene, también usa la capa pero con duración mínima (15 min)
    para mostrar todos los huecos posibles — esto evita el bug de "solo
    aparecen slots cada hora" cuando el JS no envía el servicio.
    """
    from . import services as svc

    worker = get_object_or_404(Trabajadora, nickname=nickname, activa=True)
    fecha_str = request.GET.get("fecha")
    servicio_id = request.GET.get("servicio")

    if not fecha_str:
        return HttpResponseBadRequest("The fecha parameter is required.")
    try:
        fecha = _date.fromisoformat(fecha_str)
    except ValueError:
        return HttpResponseBadRequest("Invalid date format.")
    
    # ── LÍNEA 154: VALIDACIÓN - rechazar fechas pasadas ──
    # Las horas pasadas del día actual se filtran automáticamente en
    # _slots_disponibles() línea 37 y _generar_slots_con_duracion() línea 223
    if fecha < _date.today():
        return JsonResponse({
            "slots": [],
            "error": "Cannot book appointments in the past.",
            "razon": "fecha_pasada"
        }, status=400)
    
    if fecha > _date.today() + timedelta(days=VENTANA_RESERVA_DIAS):
        return JsonResponse({"slots": [], "razon": "fuera_de_ventana"})

    duracion_usada = None
    if servicio_id:
        try:
            servicio_id_int = int(servicio_id)
            slots = svc.slots_disponibles_trabajadora(worker, fecha, servicio_id_int)
            duracion_usada = svc.duracion_para(worker.pk, servicio_id_int)
        except (ValueError, TypeError):
            slots = []
    else:
        # Sin servicio: tomamos la duración MÍNIMA que la trabajadora ofrece
        # para mostrar el máximo de slots posibles. Si no tiene servicios,
        # caemos al fallback simple.
        from django.db.models import Min
        from .models import TrabajadoraServicio
        agg = TrabajadoraServicio.objects.filter(
            trabajadora=worker, activo=True,
        ).aggregate(min_dur=Min("duracion_minutos"))
        if agg["min_dur"]:
            slots = _generar_slots_con_duracion(worker, fecha, agg["min_dur"])
            duracion_usada = agg["min_dur"]
        else:
            slots = _slots_disponibles(worker, fecha)

    response = JsonResponse({
        "fecha": fecha.isoformat(),
        "slots": [s.strftime("%H:%M") for s in slots],
        "duracion_usada": duracion_usada,
    })
    # Evitar caché del browser
    response["Cache-Control"] = "no-store, max-age=0"
    return response


def _generar_slots_con_duracion(trabajadora, fecha, duracion):
    """Genera slots libres respetando duración explícita (sin servicio).
    Usado cuando JS no envía servicio pero queremos comportamiento correcto.
    """
    from . import services as svc

    es_hoy = fecha == _date.today()
    # ✅ FILTRADO AUTOMÁTICO: Si es hoy, excluir horas pasadas
    ahora_min = svc._to_minutes(datetime.now().time()) if es_hoy else 0
    slots = []
    for h_ini, h_fin in svc.huecos_libres_trabajadora(trabajadora, fecha):
        if h_fin - h_ini < duracion:
            continue
        cursor = h_ini
        ultimo = h_fin - duracion
        while cursor <= ultimo:
            if cursor >= ahora_min:
                slots.append(svc._from_minutes(cursor))
            cursor += svc.STEP_MINUTES
    return slots


@require_http_methods(["GET", "POST"])
def confirmar_cita(request, nickname, fecha, hora):
    """Si viene ?servicio=ID, prerellena ese servicio y usa la disponibilidad
    real con duración por par (trabajadora, servicio)."""
    from . import services as svc

    worker = get_object_or_404(Trabajadora, nickname=nickname, activa=True)
    try:
        fecha_obj = _date.fromisoformat(fecha)
        hora_obj = datetime.strptime(hora, "%H-%M").time()
    except ValueError:
        return redirect("bookings:worker_detail", nickname=nickname)

    # ── LÍNEA 232: VALIDACIÓN - rechazar fechas Y horas pasadas ──
    logger.info(f"🔄 GET confirmar_cita: {worker.nickname} | {fecha_obj} {hora_obj}")
    es_valida, mensaje_error = _validar_fecha_hora_futura(fecha_obj, hora_obj)
    if not es_valida:
        messages.error(request, mensaje_error)
        logger.warning(f"❌ GET rechazado: {mensaje_error}")
        return redirect("bookings:worker_detail", nickname=nickname)

    servicio_id = request.GET.get("servicio") or request.POST.get("servicio_pref")
    servicio_pre = None
    if servicio_id:
        try:
            servicio_pre = Servicio.objects.get(pk=int(servicio_id), activo=True)
        except (Servicio.DoesNotExist, ValueError, TypeError):
            servicio_pre = None

    # Validar que el slot siga libre — usando duración real si la conocemos.
    if servicio_pre:
        libres = svc.slots_disponibles_trabajadora(worker, fecha_obj, servicio_pre.pk)
    else:
        libres = _slots_disponibles(worker, fecha_obj)

    if hora_obj not in libres:
        logger.warning(f"❌ Slot ocupado: {hora_obj} no está en slots libres")
        return render(
            request,
            "bookings/slot_taken.html",
            {"worker": worker, "fecha": fecha_obj, "hora": hora_obj},
            status=409,
        )

    initial = {"servicio": servicio_pre.pk} if servicio_pre else {}

    if request.method == "POST":
        # ── VALIDACIÓN ADICIONAL EN POST: verificar de nuevo fecha/hora ──
        logger.info(f"💾 POST confirmar_cita: {worker.nickname} | {fecha_obj} {hora_obj}")
        es_valida_post, mensaje_error_post = _validar_fecha_hora_futura(fecha_obj, hora_obj)
        if not es_valida_post:
            messages.error(request, mensaje_error_post)
            logger.warning(f"❌ POST rechazado: {mensaje_error_post}")
            return redirect("bookings:worker_detail", nickname=nickname)
        
        form = ConfirmarCitaForm(
            request.POST, trabajadora=worker, fecha=fecha_obj, hora=hora_obj
        )
        if form.is_valid():
            try:
                # ── VALIDACIÓN TRIPLE: Antes de save() ──
                es_valida_save, mensaje_error_save = _validar_fecha_hora_futura(fecha_obj, hora_obj)
                if not es_valida_save:
                    messages.error(request, mensaje_error_save)
                    logger.error(f"❌ SAVE bloqueado: {mensaje_error_save}")
                    return redirect("bookings:worker_detail", nickname=nickname)
                
                cita = form.save()
                logger.info(f"✅ Cita creada: {cita.pk} | {fecha_obj} {hora_obj}")
                return redirect(reverse("bookings:exito", args=[cita.pk]))
            except ValidationError as e:
                # Capturar errores de validación del modelo
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{field.title()}: {error}")
                        logger.error(f"❌ ValidationError: {field} - {error}")
                # Re-renderizar el formulario con los errores
    else:
        form = ConfirmarCitaForm(
            initial=initial, trabajadora=worker, fecha=fecha_obj, hora=hora_obj
        )

    return render(
        request,
        "bookings/booking_confirm.html",
        {
            "worker": worker, "fecha": fecha_obj, "hora": hora_obj, "form": form,
            "es_sin_preferencia": False,
            "servicio_pre": servicio_pre,
        },
    )


# ─────────────────────────────────────────────────────────────────────────
# B. FLUJO "SIN PREFERENCIA" (no conoce a nadie)
# ─────────────────────────────────────────────────────────────────────────
@require_GET
def cualquiera_detail(request):
    """Calendario agregado: días donde alguien está disponible."""
    return render(
        request,
        "bookings/cualquiera_detail.html",
        {
            "dias_con_horario": _dias_con_horario_global(),
            "ventana_dias": VENTANA_RESERVA_DIAS,
            "hoy": _date.today(),
        },
    )


@require_GET
def cualquiera_slots(request):
    """JSON: todos los slots donde al menos una trabajadora está libre."""
    fecha_str = request.GET.get("fecha")
    if not fecha_str:
        return HttpResponseBadRequest("The fecha parameter is required.")
    try:
        fecha = _date.fromisoformat(fecha_str)
    except ValueError:
        return HttpResponseBadRequest("Invalid date format.")
    
    # ── LÍNEA 322: VALIDACIÓN - rechazar fechas pasadas ──
    # Las horas pasadas del día actual se filtran automáticamente en
    # _slots_agregados() que llama a _slots_disponibles() línea 37
    if fecha < _date.today():
        return JsonResponse({
            "slots": [],
            "error": "Cannot book appointments in the past.",
            "razon": "fecha_pasada"
        }, status=400)
    
    if fecha > _date.today() + timedelta(days=VENTANA_RESERVA_DIAS):
        return JsonResponse({"slots": [], "razon": "fuera_de_ventana"})

    agregado = _slots_agregados(fecha)
    slots_ordenados = sorted(agregado.keys())
    return JsonResponse({
        "fecha": fecha.isoformat(),
        "slots": [s.strftime("%H:%M") for s in slots_ordenados],
    })


@require_http_methods(["GET", "POST"])
def cualquiera_confirmar(request, fecha, hora):
    """Confirma cita 'sin preferencia'. El sistema asigna trabajadora libre."""
    try:
        fecha_obj = _date.fromisoformat(fecha)
        hora_obj = datetime.strptime(hora, "%H-%M").time()
    except ValueError:
        return redirect("bookings:cualquiera_detail")

    # ── LÍNEA 350: VALIDACIÓN - rechazar fechas Y horas pasadas ──
    logger.info(f"🔄 GET cualquiera_confirmar: {fecha_obj} {hora_obj}")
    es_valida, mensaje_error = _validar_fecha_hora_futura(fecha_obj, hora_obj)
    if not es_valida:
        messages.error(request, mensaje_error)
        logger.warning(f"❌ GET rechazado: {mensaje_error}")
        return redirect("bookings:cualquiera_detail")

    elegida = _elegir_trabajadora_libre(fecha_obj, hora_obj)
    if elegida is None:
        logger.warning(f"❌ No hay trabajadora libre para {fecha_obj} {hora_obj}")
        return render(
            request,
            "bookings/slot_taken.html",
            {"worker": None, "fecha": fecha_obj, "hora": hora_obj},
            status=409,
        )

    if request.method == "POST":
        # ── VALIDACIÓN ADICIONAL EN POST: verificar de nuevo fecha/hora ──
        logger.info(f"💾 POST cualquiera_confirmar: {fecha_obj} {hora_obj}")
        es_valida_post, mensaje_error_post = _validar_fecha_hora_futura(fecha_obj, hora_obj)
        if not es_valida_post:
            messages.error(request, mensaje_error_post)
            logger.warning(f"❌ POST rechazado: {mensaje_error_post}")
            return redirect("bookings:cualquiera_detail")
        
        # Re-elegir al guardar (por si se ocupó entre GET y POST).
        elegida_post = _elegir_trabajadora_libre(fecha_obj, hora_obj)
        if elegida_post is None:
            logger.warning(f"❌ POST: No hay trabajadora libre para {fecha_obj} {hora_obj}")
            return render(
                request, "bookings/slot_taken.html",
                {"worker": None, "fecha": fecha_obj, "hora": hora_obj},
                status=409,
            )
        form = ConfirmarCitaForm(
            request.POST,
            trabajadora=elegida_post, fecha=fecha_obj, hora=hora_obj,
        )
        if form.is_valid():
            try:
                # ── VALIDACIÓN TRIPLE: Antes de save() ──
                es_valida_save, mensaje_error_save = _validar_fecha_hora_futura(fecha_obj, hora_obj)
                if not es_valida_save:
                    messages.error(request, mensaje_error_save)
                    logger.error(f"❌ SAVE bloqueado: {mensaje_error_save}")
                    return redirect("bookings:cualquiera_detail")
                
                cita = form.save()
                logger.info(f"✅ Cita creada: {cita.pk} | {fecha_obj} {hora_obj}")
                return redirect(reverse("bookings:exito", args=[cita.pk]))
            except ValidationError as e:
                # Capturar errores de validación del modelo
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{field.title()}: {error}")
                        logger.error(f"❌ ValidationError: {field} - {error}")
                # Re-renderizar el formulario con los errores
    else:
        form = ConfirmarCitaForm(
            trabajadora=elegida, fecha=fecha_obj, hora=hora_obj
        )

    return render(
        request,
        "bookings/booking_confirm.html",
        {
            "worker": elegida,  # se mostrará pero el cliente no la "eligió"
            "fecha": fecha_obj, "hora": hora_obj, "form": form,
            "es_sin_preferencia": True,
        },
    )


# ─────────────────────────────────────────────────────────────────────────
# Página de éxito
# ─────────────────────────────────────────────────────────────────────────
@require_GET
def exito(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    return render(request, "bookings/booking_success.html", {"cita": cita})
