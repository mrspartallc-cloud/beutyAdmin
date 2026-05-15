"""
Vistas del panel administrativo (back-office).

Acceso: SOLO superusers / staff (`is_staff`).
Las trabajadoras NO inician sesión — toda la gestión la hace el administrador:
- Crear / editar trabajadoras
- Configurar disponibilidad de cada trabajadora
- Aceptar / rechazar / completar citas
- Asignar trabajadora a citas "sin preferencia"
- Registrar ingresos
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from bookings.forms import HorarioDisponibleForm
from bookings.models import Cita, HorarioDisponible
from core.models import Servicio

from .forms import RegistroForm, TrabajadoraForm
from .models import Registro, Trabajadora


# ── Decorador único: solo staff ──────────────────────────────────────────
def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Your user does not have admin permissions.")
            return redirect("panel:login")
        return view(request, *args, **kwargs)
    return wrapper


# ═════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def dashboard(request):
    registros = Registro.objects.select_related("trabajadora").order_by("-fecha")
    agg = registros.aggregate(
        total_clientes=Sum("monto_original"),
        total_trabajadoras=Sum("monto"),
        total_propinas=Sum("propina"),
    )
    metrics = {
        "n_registros": registros.count(),
        "total_clientes": agg["total_clientes"] or Decimal("0"),
        "total_trabajadoras": agg["total_trabajadoras"] or Decimal("0"),
        "total_propinas": agg["total_propinas"] or Decimal("0"),
        "ganancia_spa": (agg["total_clientes"] or Decimal("0"))
        - (agg["total_trabajadoras"] or Decimal("0")),
        "citas_pendientes": Cita.objects.filter(estado=Cita.ESTADO_PENDIENTE).count(),
        "citas_sin_asignar": Cita.objects.filter(
            trabajadora__isnull=True
        ).exclude(estado=Cita.ESTADO_CANCELADA).count(),
    }
    return render(
        request, "panel/dashboard.html",
        {"registros": registros, "metrics": metrics},
    )


# ═════════════════════════════════════════════════════════════════════════
# TRABAJADORAS — CRUD + gestión de disponibilidad
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def trabajadoras_list(request):
    return render(
        request, "panel/trabajadoras_list.html",
        {"trabajadoras": Trabajadora.objects.all()},
    )


@staff_required
def trabajadora_create(request):
    form = TrabajadoraForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Technician added successfully.")
        return redirect("panel:trabajadoras_list")
    return render(
        request, "panel/trabajadora_form.html",
        {"form": form, "modo": "crear", "titulo": "New technician"},
    )


@staff_required
def trabajadora_update(request, pk):
    obj = get_object_or_404(Trabajadora, pk=pk)
    form = TrabajadoraForm(
        request.POST or None, request.FILES or None, instance=obj
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Technician updated.")
        return redirect("panel:trabajadoras_list")
    return render(
        request, "panel/trabajadora_form.html",
        {"form": form, "modo": "editar", "obj": obj, "titulo": "Edit technician"},
    )


@staff_required
def trabajadora_delete(request, pk):
    obj = get_object_or_404(Trabajadora, pk=pk)
    if request.method == "POST":
        nombre = obj.nombre_completo
        obj.delete()
        messages.warning(request, f'Technician "{nombre}" deleted.')
        return redirect("panel:trabajadoras_list")
    return render(
        request, "panel/confirmar_eliminar.html",
        {
            "obj": obj,
            "titulo": "Delete technician",
            "advertencia": "All appointments and records will also be removed.",
            "url_cancelar": "panel:trabajadoras_list",
        },
    )


@staff_required
def trabajadora_disponibilidad(request, pk):
    """Admin gestiona los bloques de disponibilidad de una trabajadora."""
    worker = get_object_or_404(Trabajadora, pk=pk)
    horarios = worker.horarios_disponibles.all().order_by(
        "dia_semana", "hora_inicio"
    )

    if request.method == "POST":
        form = HorarioDisponibleForm(request.POST)
        if form.is_valid():
            h = form.save(commit=False)
            h.trabajadora = worker
            h.save()
            messages.success(
                request,
                f"Bloque agregado a @{worker.nickname}.",
            )
            return redirect("panel:trabajadora_disponibilidad", pk=worker.pk)
    else:
        form = HorarioDisponibleForm()

    return render(
        request, "panel/trabajadora_disponibilidad.html",
        {"worker": worker, "horarios": horarios, "form": form},
    )


@staff_required
def horario_eliminar(request, pk):
    h = get_object_or_404(HorarioDisponible, pk=pk)
    worker_pk = h.trabajadora_id
    if request.method == "POST":
        h.delete()
        messages.warning(request, "Schedule block deleted.")
        return redirect("panel:trabajadora_disponibilidad", pk=worker_pk)
    return render(
        request, "panel/confirmar_eliminar.html",
        {
            "obj": h,
            "titulo": "Delete schedule block",
            "advertencia": "Appointments already booked in this block will NOT be auto-cancelled.",
            "url_cancelar": "panel:trabajadora_disponibilidad",
            "url_cancelar_arg": worker_pk,
        },
    )


@staff_required
def horario_toggle(request, pk):
    h = get_object_or_404(HorarioDisponible, pk=pk)
    h.activo = not h.activo
    h.save(update_fields=["activo"])
    return redirect("panel:trabajadora_disponibilidad", pk=h.trabajadora_id)


# ═════════════════════════════════════════════════════════════════════════
# INGRESOS
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def ingreso_create(request):
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        r = form.save()
        messages.success(
            request,
            f"Income recorded: ${r.total} for {r.trabajadora.display_name}.",
        )
        return redirect("panel:dashboard")
    return render(
        request, "panel/ingreso_form.html",
        {"form": form, "modo": "crear", "titulo": "New income"},
    )


@staff_required
def ingreso_update(request, pk):
    r = get_object_or_404(Registro, pk=pk)
    form = RegistroForm(request.POST or None, instance=r)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Income record updated.")
        return redirect("panel:dashboard")
    return render(
        request, "panel/ingreso_form.html",
        {"form": form, "modo": "editar", "obj": r, "titulo": "Edit income"},
    )


@staff_required
def ingreso_delete(request, pk):
    r = get_object_or_404(Registro, pk=pk)
    if request.method == "POST":
        r.delete()
        messages.warning(request, "Income record deleted.")
        return redirect("panel:dashboard")
    return render(
        request, "panel/confirmar_eliminar.html",
        {
            "obj": r,
            "titulo": "Delete income",
            "advertencia": "This action cannot be undone.",
            "url_cancelar": "panel:dashboard",
        },
    )


# RESUMEN FINANCIERO PREMIUM - Vista con datos para Chart.js
# ═════════════════════════════════════════════════════════════════════════
# 📍 Agregar esta función al final de panel/views.py (reemplazar la existente)

import json
from datetime import datetime, timedelta

@staff_required
def resumen(request):
    """Resumen financiero con gráficas Chart.js y métricas avanzadas."""
    from django.db.models.functions import TruncDate
    
    # ── Filtros ──────────────────────────────────────────────────────────
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    filtro_trabajadora = request.GET.get('trabajadora')
    
    # Fechas por defecto: últimos 30 días
    if fecha_fin_str:
        try:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_fin = date.today()
    else:
        fecha_fin = date.today()
    
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_inicio = fecha_fin - timedelta(days=30)
    else:
        fecha_inicio = fecha_fin - timedelta(days=30)
    
    # ── QuerySet Base ────────────────────────────────────────────────────
    qs = Registro.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin
    )
    
    if filtro_trabajadora:
        qs = qs.filter(trabajadora_id=filtro_trabajadora)
    
    # ── Datos por Trabajadora ────────────────────────────────────────────
    por_trabajadora = list(
        qs.values("fecha", "trabajadora__nickname", "trabajadora__nombre_completo")
        .annotate(
            monto_original_total=Sum("monto_original"),
            monto_total=Sum("monto"),
            propina_total=Sum("propina"),
            total_final=Sum("total"),
        )
        .order_by("-fecha", "trabajadora__nickname")
    )
    
    # Rename fecha -> dia for template compatibility
    for r in por_trabajadora:
        r["dia"] = r.pop("fecha")
    
    # ── Suma Diaria ──────────────────────────────────────────────────────
    suma_diaria_qs = (
        qs.values("fecha")
        .annotate(
            total_clientes=Sum("monto_original"),
            total_trabajadoras=Sum("monto"),
            total_propinas=Sum("propina"),
        )
        .order_by("fecha")  # ← Ordenar ASC para gráficas
    )
    
    suma_diaria = []
    for s in suma_diaria_qs:
        s["dia"] = s["fecha"]
        ganancia = (s["total_clientes"] or Decimal("0")) - (
            s["total_trabajadoras"] or Decimal("0")
        )
        s["ganancia_spa"] = ganancia
        suma_diaria.append(s)
    
    # ── Métricas Generales ───────────────────────────────────────────────
    agg = qs.aggregate(
        total_clientes=Sum("monto_original"),
        total_trabajadoras=Sum("monto"),
        total_propinas=Sum("propina"),
        num_registros=Count("pk"),
    )
    
    total_clientes = agg["total_clientes"] or Decimal("0")
    total_trabajadoras = agg["total_trabajadoras"] or Decimal("0")
    total_propinas = agg["total_propinas"] or Decimal("0")
    ganancia_spa = total_clientes - total_trabajadoras
    
    # Cálculos adicionales
    margen_spa = (ganancia_spa / total_clientes * 100) if total_clientes > 0 else 0
    avg_propina = (total_propinas / total_trabajadoras * 100) if total_trabajadoras > 0 else 0
    
    metricas = {
        "total_clientes": total_clientes,
        "total_trabajadoras": total_trabajadoras,
        "total_propinas": total_propinas,
        "ganancia_spa": ganancia_spa,
        "margen_spa": margen_spa,
        "avg_propina": avg_propina,
        "num_registros": agg["num_registros"],
    }
    
    # ── Datos para Gráfica Daily Revenue ─────────────────────────────────
    chart_daily = {
        "labels": [s["dia"].strftime("%m/%d") for s in suma_diaria],
        "revenue": [float(s["total_clientes"]) for s in suma_diaria],
        "profit": [float(s["ganancia_spa"]) for s in suma_diaria],
    }
    
    # ── Datos para Gráfica Top Technicians ───────────────────────────────
    top_techs = (
        qs.values("trabajadora__nickname")
        .annotate(total_revenue=Sum("monto_original"))
        .order_by("-total_revenue")[:10]
    )
    
    chart_techs = {
        "labels": ["@" + t["trabajadora__nickname"] for t in top_techs],
        "values": [float(t["total_revenue"]) for t in top_techs],
    }
    
    # ── Datos para Gráfica Breakdown (Doughnut) ──────────────────────────
    chart_breakdown = {
        "labels": ["Tech Pay", "Spa Profit", "Tips"],
        "values": [
            float(total_trabajadoras),
            float(ganancia_spa),
            float(total_propinas),
        ],
    }
    
    # ── Render ───────────────────────────────────────────────────────────
    return render(
        request, "panel/resumen.html",
        {
            "resultados": por_trabajadora,
            "suma_diaria": suma_diaria,
            "por_trabajadora": por_trabajadora,
            "metricas": metricas,
            "trabajadoras": Trabajadora.objects.filter(activa=True),
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "filtro_trabajadora": filtro_trabajadora,
            # JSON para Chart.js
            "chart_daily_json": json.dumps(chart_daily),
            "chart_techs_json": json.dumps(chart_techs),
            "chart_breakdown_json": json.dumps(chart_breakdown),
        },
    )

# ═════════════════════════════════════════════════════════════════════════
# CITAS (administración global)
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def citas_admin(request):
    """Tabla de TODAS las citas con filtros + acciones."""
    qs = Cita.objects.select_related("trabajadora", "servicio").order_by(
        "-fecha", "-hora"
    )
    estado = request.GET.get("estado")
    if estado:
        qs = qs.filter(estado=estado)
    nick = request.GET.get("nick")
    if nick == "__sin__":
        qs = qs.filter(trabajadora__isnull=True)
    elif nick:
        qs = qs.filter(trabajadora__nickname=nick)

    estados_count = {
        c["estado"]: c["n"]
        for c in Cita.objects.values("estado").annotate(n=Count("pk"))
    }

    sin_asignar = Cita.objects.filter(
        trabajadora__isnull=True
    ).exclude(estado=Cita.ESTADO_CANCELADA).count()

    return render(
        request, "panel/citas_admin.html",
        {
            "citas": qs,
            "filtro_estado": estado,
            "filtro_nick": nick,
            "trabajadoras": Trabajadora.objects.filter(activa=True),
            "estados": Cita.ESTADO_CHOICES,
            "estados_count": estados_count,
            "sin_asignar_count": sin_asignar,
        },
    )


@staff_required
def cita_aceptar(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    if cita.trabajadora is None:
        messages.warning(
            request,
            "Asigna una trabajadora antes de confirmar la cita.",
        )
        return redirect("panel:cita_asignar", pk=pk)
    if cita.estado in (Cita.ESTADO_PENDIENTE,):
        cita.estado = Cita.ESTADO_CONFIRMADA
        
        print("   ********************** DEBUG: Saving cita with estado=CONFIRMADA" \
        " enla linia 445 de view panel se puede incluir la opccion de enviar mensaje telefono o correo  "
        " *********")
        
        cita.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"Appointment confirmed for {cita.fecha:%m/%d/%Y}.")
    return redirect("panel:citas_admin")


@staff_required
def cita_rechazar(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    if cita.estado != Cita.ESTADO_CANCELADA:
        cita.estado = Cita.ESTADO_CANCELADA
        cita.save(update_fields=["estado", "actualizado"])
        messages.warning(request, "Appointment cancelled.")
    return redirect("panel:citas_admin")


@staff_required
def cita_completar(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    cita.estado = Cita.ESTADO_COMPLETADA
    cita.save(update_fields=["estado", "actualizado"])
    messages.success(request, "Appointment marked as completed.")
    return redirect("panel:citas_admin")


@staff_required
def cita_asignar(request, pk):
    """Asignar trabajadora a una cita 'sin preferencia'."""
    cita = get_object_or_404(Cita, pk=pk)

    # Sugerir trabajadoras que tienen ese día/hora libre.
    candidatas = []
    if cita.fecha and cita.hora:
        dia = cita.fecha.weekday()
        for t in Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True):
            tiene_bloque = HorarioDisponible.objects.filter(
                trabajadora=t,
                dia_semana=dia,
                activo=True,
                hora_inicio__lte=cita.hora,
                hora_fin__gt=cita.hora,
            ).exists()
            if not tiene_bloque:
                continue
            ocupada = Cita.objects.filter(
                trabajadora=t, fecha=cita.fecha, hora=cita.hora,
            ).exclude(estado=Cita.ESTADO_CANCELADA).exclude(pk=cita.pk).exists()
            if not ocupada:
                candidatas.append(t)

    if request.method == "POST":
        nueva_pk = request.POST.get("trabajadora_id")
        if nueva_pk:
            trab = get_object_or_404(Trabajadora, pk=nueva_pk)
            cita.trabajadora = trab
            try:
                cita.full_clean()
                cita.save()
                messages.success(
                    request,
                    f"Cita asignada a @{trab.nickname}.",
                )
                return redirect("panel:citas_admin")
            except Exception as exc:
                messages.error(request, f"Unable to assign: {exc}")

    return render(
        request, "panel/cita_asignar.html",
        {
            "cita": cita,
            "candidatas": candidatas,
            "todas": Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True),
        },
    )


@staff_required
def calendario_admin(request):
    """Vista semanal de citas, agrupadas por trabajadora y hora."""
    try:
        offset = int(request.GET.get("w", "0"))
    except ValueError:
        offset = 0

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=offset)
    dias = [inicio_semana + timedelta(days=i) for i in range(7)]

    citas_qs = (
        Cita.objects.filter(fecha__gte=dias[0], fecha__lte=dias[-1])
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("trabajadora", "servicio")
        .order_by("fecha", "hora")
    )

    seen, colisiones = {}, set()
    for c in citas_qs:
        if c.trabajadora_id is None:
            continue
        key = (c.trabajadora_id, c.fecha, c.hora)
        if key in seen:
            colisiones.add(c.pk)
            colisiones.add(seen[key])
        else:
            seen[key] = c.pk

    grid = {}
    for c in citas_qs:
        if c.trabajadora_id is None:
            continue
        grid.setdefault(c.trabajadora, {})[(c.fecha, c.hora)] = c

    return render(
        request, "panel/calendario_admin.html",
        {
            "dias": dias,
            "grid": grid,
            "colisiones": colisiones,
            "offset": offset,
            "anterior": offset - 1,
            "siguiente": offset + 1,
            "es_actual": offset == 0,
            "n_total": citas_qs.count(),
        },
    )


# ═════════════════════════════════════════════════════════════════════════
# 🚀 QUICK MODE — vistas optimizadas para móvil (iPhone / S23)
#    Diseñadas para registrar una cita en <15 segundos durante una llamada.
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def quick_home(request):
    """Vista principal móvil: lista de citas de HOY + FAB para nueva cita."""
    hoy = date.today()
    ahora = datetime.now().time()

    # Filtro: hoy o mañana
    cuando = request.GET.get("d", "hoy")
    if cuando == "manana":
        fecha_filtro = hoy + timedelta(days=1)
        titulo = "Tomorrow"
    else:
        fecha_filtro = hoy
        titulo = "Today"
        cuando = "hoy"

    citas = (
        Cita.objects.filter(fecha=fecha_filtro)
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("trabajadora", "servicio")
        .order_by("hora")
    )

    # Resaltar la siguiente cita (más próxima futura) si es hoy
    siguiente_pk = None
    if cuando == "hoy":
        for c in citas:
            if c.hora >= ahora and c.estado != Cita.ESTADO_COMPLETADA:
                siguiente_pk = c.pk
                break

    pendientes_total = Cita.objects.filter(
        estado=Cita.ESTADO_PENDIENTE
    ).count()

    return render(
        request, "panel/quick_home.html",
        {
            "citas": citas,
            "fecha": fecha_filtro,
            "titulo": titulo,
            "cuando": cuando,
            "siguiente_pk": siguiente_pk,
            "pendientes_total": pendientes_total,
            "n_citas": citas.count(),
        },
    )


def _proximo_slot_libre(trabajadora=None, fecha=None):
    """Devuelve el siguiente slot disponible (datetime) desde ahora.

    Si trabajadora=None, busca cualquier trabajadora libre.
    Si fecha=None, empieza desde hoy.
    """
    fecha = fecha or date.today()
    ahora = datetime.now().time()

    workers = (
        [trabajadora]
        if trabajadora
        else list(Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True))
    )
    if not workers:
        return None, None

    # Buscar hasta 14 días al futuro
    for offset in range(15):
        f = fecha + timedelta(days=offset)
        dia = f.weekday()
        # Recolectar slots posibles para todas las trabajadoras
        slots_por_worker = []
        for w in workers:
            bloques = HorarioDisponible.objects.filter(
                trabajadora=w, dia_semana=dia, activo=True,
            )
            slots = []
            for b in bloques:
                slots.extend(b.generar_slots())
            ocupados = set(
                Cita.objects.filter(trabajadora=w, fecha=f)
                .exclude(estado=Cita.ESTADO_CANCELADA)
                .values_list("hora", flat=True)
            )
            for s in slots:
                if s in ocupados:
                    continue
                if offset == 0 and s <= ahora:
                    continue
                slots_por_worker.append((s, w))
        if slots_por_worker:
            slots_por_worker.sort(key=lambda x: x[0])
            slot, w = slots_por_worker[0]
            return (datetime.combine(f, slot), w)
    return None, None


def _seleccionar_auto(fecha, hora, servicio_id=None):
    """Trabajadora con menos citas ese día, libre y que ofrece el servicio.

    Si se pasa servicio_id, usa la capa de servicios (considera duración).
    Si no, usa la lógica simple anterior.
    """
    if servicio_id:
        from bookings import services as svc
        return svc.elegir_trabajadora_libre(servicio_id, fecha, hora)

    # Fallback (sin servicio): respeta horarios pero ignora duración
    dia = fecha.weekday()
    candidatas = []
    for w in Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True):
        tiene_bloque = HorarioDisponible.objects.filter(
            trabajadora=w, dia_semana=dia, activo=True,
            hora_inicio__lte=hora, hora_fin__gt=hora,
        ).exists()
        if not tiene_bloque:
            continue
        ocupada = Cita.objects.filter(
            trabajadora=w, fecha=fecha, hora=hora,
        ).exclude(estado=Cita.ESTADO_CANCELADA).exists()
        if not ocupada:
            candidatas.append(w)
    if not candidatas:
        return None
    candidatas.sort(
        key=lambda w: Cita.objects.filter(trabajadora=w, fecha=fecha)
        .exclude(estado=Cita.ESTADO_CANCELADA).count()
    )
    return candidatas[0]


@staff_required
def quick_new(request):
    """Pantalla rápida para crear cita. Form único minimal."""
    # Si vienen ?fecha=YYYY-MM-DD&hora=HH:MM en GET, los pre-rellenamos.
    fecha_pre = request.GET.get("fecha")
    hora_pre = request.GET.get("hora")

    # Sugerencias precargadas
    proximo_dt, proxima_worker = _proximo_slot_libre()
    fecha_sugerida = proximo_dt.date() if proximo_dt else date.today()
    hora_sugerida = proximo_dt.time() if proximo_dt else None

    # Si vinieron pre-fill desde calendario, sobrescribir sugerencias
    if fecha_pre:
        try:
            fecha_sugerida = date.fromisoformat(fecha_pre)
        except ValueError:
            pass
    if hora_pre:
        try:
            hora_sugerida = datetime.strptime(hora_pre, "%H:%M").time()
        except ValueError:
            pass

    # Para datalist de clientes recientes (autocompletado)
    clientes_recientes = list(
        Cita.objects.values_list("nombre_cliente", flat=True)
        .distinct().order_by("-creado")[:30]
    )

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        telefono = (request.POST.get("telefono") or "").strip()
        servicio_id = request.POST.get("servicio")
        trabajadora_id = request.POST.get("trabajadora") or ""
        fecha_str = request.POST.get("fecha")
        hora_str = request.POST.get("hora")
        notas = (request.POST.get("notas") or "").strip()

        # Parse fecha/hora
        try:
            fecha_obj = date.fromisoformat(fecha_str) if fecha_str else date.today()
            hora_obj = datetime.strptime(hora_str, "%H:%M").time() if hora_str else hora_sugerida
        except (ValueError, TypeError):
            messages.error(request, "Invalid date or time.")
            return redirect("panel:quick_new")

        # ── VALIDACIÓN: rechazar fechas Y horas pasadas ──
        hoy = date.today()
        ahora = datetime.now()
        if fecha_obj < hoy:
            messages.error(request, "Cannot book appointments in the past. Please select a future date.")
            return redirect("panel:quick_new")
        if fecha_obj == hoy and hora_obj:
            fecha_hora_cita = datetime.combine(fecha_obj, hora_obj)
            if fecha_hora_cita <= ahora:
                messages.error(request, "Cannot book appointments for past times. Please select a future time.")
                return redirect("panel:quick_new")

        # Solo nombre, servicio y hora son obligatorios. Teléfono es opcional.
        if not (nombre and servicio_id and hora_obj):
            messages.error(request, "Missing required fields: name, service, and time.")
            return redirect("panel:quick_new")

        try:
            servicio = Servicio.objects.get(pk=servicio_id, activo=True)
        except Servicio.DoesNotExist:
            messages.error(request, "Invalid service.")
            return redirect("panel:quick_new")

        # Trabajadora: si "Auto" o vacío, intenta asignar la menos cargada.
        # Si no hay candidatas (porque ninguna tiene horario en ese slot),
        # deja la cita sin asignar — la dueña la asigna después manualmente.
        trabajadora = None
        if trabajadora_id and trabajadora_id != "auto":
            trabajadora = Trabajadora.objects.filter(pk=trabajadora_id, activa=True).first()
        if not trabajadora and (not trabajadora_id or trabajadora_id == "auto"):
            trabajadora = _seleccionar_auto(fecha_obj, hora_obj, servicio_id=servicio_id)
            # Si la lógica con duración falla (nadie disponible), intenta
            # sin duración (asignación más laxa).
            if not trabajadora:
                trabajadora = _seleccionar_auto(fecha_obj, hora_obj)
            # Última red de seguridad: cualquier trabajadora activa sin
            # conflicto exacto en esa hora.
            if not trabajadora:
                ocupadas_ids = set(
                    Cita.objects.filter(fecha=fecha_obj, hora=hora_obj)
                    .exclude(estado=Cita.ESTADO_CANCELADA)
                    .values_list("trabajadora_id", flat=True)
                )
                trabajadora = (
                    Trabajadora.objects.filter(activa=True)
                    .exclude(nickname__isnull=True)
                    .exclude(pk__in=ocupadas_ids)
                    .first()
                )

        cita = Cita(
            nombre_cliente=nombre,
            telefono=telefono,
            servicio=servicio,
            trabajadora=trabajadora,
            fecha=fecha_obj,
            hora=hora_obj,
            notas=notas,
            estado=Cita.ESTADO_CONFIRMADA,
        )
        # Auto-rellenamos la duración antes de validar solapamientos.
        cita._autorelenar_duracion()
        try:
            if trabajadora:
                ini_min = hora_obj.hour * 60 + hora_obj.minute
                fin_min = ini_min + (cita.duracion_minutos or 60)
                otras = Cita.objects.filter(
                    trabajadora=trabajadora, fecha=fecha_obj,
                ).exclude(estado=Cita.ESTADO_CANCELADA)
                for o in otras:
                    o_ini = o.hora.hour * 60 + o.hora.minute
                    o_fin = o_ini + (o.duracion_minutos or 60)
                    if ini_min < o_fin and o_ini < fin_min:
                        messages.error(
                            request,
                            f"@{trabajadora.nickname} already has an appointment "
                            f"at {o.hora:%H:%M} ({o.duracion_minutos} min). "
                            "Please choose a different time.",
                        )
                        return redirect("panel:quick_new")
            cita.save()
        except Exception as exc:
            messages.error(request, f"Unable to create: {exc}")
            return redirect("panel:quick_new")

        nick = cita.trabajadora.nickname if cita.trabajadora else "(sin asignar)"
        messages.success(
            request,
            f"✓ {nombre} · {fecha_obj:%m/%d} {hora_obj:%H:%M} · @{nick}",
        )
        return redirect("panel:quick_home")

    # Lista de servicios + qué trabajadoras los hacen (para filtrado dinámico en JS).
    from bookings.models import TrabajadoraServicio
    pares_ts = list(
        TrabajadoraServicio.objects.filter(activo=True)
        .values_list("trabajadora_id", "servicio_id")
    )
    # Mapa: servicio_id → [trabajadora_id]
    servicio_a_workers = {}
    for tid, sid in pares_ts:
        servicio_a_workers.setdefault(sid, []).append(tid)

    import json
    return render(
        request, "panel/quick_new.html",
        {
            "servicios": Servicio.objects.filter(activo=True),
            "servicio_workers_json": json.dumps(servicio_a_workers),
            "trabajadoras": Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True),
            "fecha_sugerida": fecha_sugerida,
            "hora_sugerida": hora_sugerida,
            "hora_sugerida_str": hora_sugerida.strftime("%H:%M") if hora_sugerida else "",
            "fecha_sugerida_iso": fecha_sugerida.isoformat() if fecha_sugerida else "",
            "proxima_worker": proxima_worker,
            "clientes_recientes": clientes_recientes,
            "hoy_iso": date.today().isoformat(),
        },
    )


@staff_required
@require_GET
def quick_slots_json(request):
    """Endpoint AJAX: ?fecha=YYYY-MM-DD&trabajadora=ID|'auto'&servicio=ID&forzar=HH:MM

    Si viene `servicio` y trabajadora == 'auto':
        usa la capa de servicios para calcular slots con capacidad real
        (considera duración por trabajadora, solapamientos, etc.).
    Si viene una trabajadora específica:
        respeta sus bloques + duración del servicio (si se pasa).
    Si NO viene servicio, fallback al modo simple (slots cada hora).
    `forzar=HH:MM` agrega ese slot aunque no salga en el cómputo.
    """
    from bookings import services as svc

    fecha_str = request.GET.get("fecha")
    trab_id = request.GET.get("trabajadora") or "auto"
    servicio_id = request.GET.get("servicio")
    forzar_str = request.GET.get("forzar") or ""

    try:
        fecha = date.fromisoformat(fecha_str)
    except (ValueError, TypeError):
        return JsonResponse({"slots": [], "error": "invalid date"})

    forzar_time = None
    if forzar_str:
        try:
            forzar_time = datetime.strptime(forzar_str, "%H:%M").time()
        except ValueError:
            forzar_time = None

    # Caso 1: con servicio + Auto → capacidad real con duraciones
    if servicio_id and trab_id == "auto":
        agregados = svc.slots_unicos_por_hora(int(servicio_id), fecha)
        horas = [a["hora"] for a in agregados]
        if forzar_time:
            f = forzar_time.strftime("%H:%M")
            if f not in horas:
                horas.append(f)
                horas.sort()
        return JsonResponse({"fecha": fecha.isoformat(), "slots": horas})

    # Caso 2: con servicio + trabajadora específica
    if servicio_id and trab_id != "auto":
        try:
            from panel.models import Trabajadora
            w = Trabajadora.objects.get(pk=trab_id, activa=True)
        except Trabajadora.DoesNotExist:
            return JsonResponse({"slots": []})
        slots_t = svc.slots_disponibles_trabajadora(w, fecha, int(servicio_id))
        horas = sorted({s.strftime("%H:%M") for s in slots_t})
        if forzar_time:
            f = forzar_time.strftime("%H:%M")
            if f not in horas:
                horas.append(f)
                horas.sort()
        return JsonResponse({"fecha": fecha.isoformat(), "slots": horas})

    # Caso 3 (fallback): sin servicio elegido aún. Mostramos cada hora.
    ahora = datetime.now().time()
    es_hoy = fecha == date.today()
    slots_set = set()
    if trab_id == "auto":
        for hora_int in range(8, 21):
            t = time(hora_int, 0)
            if es_hoy and t <= ahora:
                continue
            slots_set.add(t)
    else:
        from panel.models import Trabajadora
        try:
            w = Trabajadora.objects.get(pk=trab_id, activa=True)
            for s in svc.slots_disponibles_trabajadora(w, fecha):
                slots_set.add(s)
        except Trabajadora.DoesNotExist:
            pass

    if forzar_time:
        slots_set.add(forzar_time)

    return JsonResponse({
        "fecha": fecha.isoformat(),
        "slots": [s.strftime("%H:%M") for s in sorted(slots_set)],
    })


@staff_required
@require_POST
def quick_complete(request, pk):
    """Marcar como completada con un toque."""
    cita = get_object_or_404(Cita, pk=pk)
    cita.estado = Cita.ESTADO_COMPLETADA
    cita.save(update_fields=["estado", "actualizado"])
    messages.success(request, f"✓ {cita.nombre_cliente}")
    return redirect("panel:quick_home")


@staff_required
@require_POST
def quick_cancel(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    cita.estado = Cita.ESTADO_CANCELADA
    cita.save(update_fields=["estado", "actualizado"])
    messages.warning(request, f"Cancelled: {cita.nombre_cliente}")
    return redirect("panel:quick_home")


# ─────────────────────────────────────────────────────────────────────────
# Quick Calendar — vista semanal grilla (días × horas) para móvil
# ─────────────────────────────────────────────────────────────────────────
@staff_required
def quick_calendar(request):
    """Calendario semanal en grilla, tipo app nativa.

    Filas = horas (8am→8pm), Columnas = días (lun→dom).
    Cada celda muestra ocupado/disponible/no-trabaja.
    """
    try:
        offset = int(request.GET.get("w", "0"))
    except ValueError:
        offset = 0

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=offset)
    dias = [inicio_semana + timedelta(days=i) for i in range(7)]

    # Rango de horas mostrado (8am - 8pm = 13 filas)
    HORA_INICIO = 8
    HORA_FIN = 20
    horas = list(range(HORA_INICIO, HORA_FIN + 1))

    # Trabajadoras activas
    workers = list(
        Trabajadora.objects.filter(activa=True).exclude(nickname__isnull=True)
    )

    # Citas de la semana (no canceladas)
    citas_semana = (
        Cita.objects.filter(
            fecha__gte=dias[0], fecha__lte=dias[-1],
        )
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("trabajadora", "servicio")
    )

    # Diccionario {(fecha, hora_int): [citas]}
    citas_por_celda = {}
    for c in citas_semana:
        key = (c.fecha, c.hora.hour)
        citas_por_celda.setdefault(key, []).append(c)

    # Diccionario {(dia_semana, hora_int): True} — hay al menos un bloque activo
    bloques_activos = set()
    for h in HorarioDisponible.objects.filter(activo=True, trabajadora__activa=True):
        for s in h.generar_slots():
            bloques_activos.add((h.dia_semana, s.hour))

    # Construir grilla: lista de filas, cada fila = lista de celdas
    grilla = []
    for h in horas:
        fila = {"hora": h, "label": _fmt_hora_12h(h), "celdas": []}
        for d in dias:
            citas = citas_por_celda.get((d, h), [])
            tiene_horario = (d.weekday(), h) in bloques_activos
            estado = "ocupada" if citas else ("libre" if tiene_horario else "cerrado")
            ahora = datetime.now()
            es_pasado = False
            if d < hoy:
                es_pasado = True
            elif d == hoy and h < ahora.hour:
                es_pasado = True
            
            fila["celdas"].append({
                "fecha": d,
                "hora": h,
                "estado": estado,
                "n_citas": len(citas),
                "citas": citas,
                "es_hoy": d == hoy,
                "es_pasado": es_pasado,
            })

        grilla.append(fila)

    return render(
        request, "panel/quick_calendar.html",
        {
            "dias": dias,
            "grilla": grilla,
            "offset": offset,
            "anterior": offset - 1,
            "siguiente": offset + 1,
            "es_actual": offset == 0,
            "mes_label": _fmt_mes_label(dias[0], dias[-1]),
            "n_citas": citas_semana.count(),
        },
    )


def _fmt_hora_12h(h):
    """8 → '8am', 13 → '1pm'."""
    if h == 0: return "12am"
    if h < 12: return f"{h}am"
    if h == 12: return "12pm"
    return f"{h - 12}pm"


def _fmt_mes_label(inicio, fin):
    """Header label: 'May 2026' or 'May–Jun 2026' if it crosses months."""
    meses = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
    if inicio.month == fin.month:
        return f"{meses[inicio.month - 1]} {inicio.year}"
    return f"{meses[inicio.month - 1]}–{meses[fin.month - 1][:3]} {fin.year}"


@staff_required
def quick_day_detail(request, fecha, hora):
    """Detalle de un slot específico del calendario semanal."""
    try:
        fecha_obj = date.fromisoformat(fecha)
        hora_int = int(hora)
    except (ValueError, TypeError):
        return redirect("panel:quick_calendar")

    citas = list(
        Cita.objects.filter(
            fecha=fecha_obj, hora__hour=hora_int,
        )
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("trabajadora", "servicio")
        .order_by("hora")
    )

    return render(
        request, "panel/quick_day_detail.html",
        {
            "fecha": fecha_obj,
            "hora_label": _fmt_hora_12h(hora_int),
            "hora_int": hora_int,
            "citas": citas,
        },
    )


# ═════════════════════════════════════════════════════════════════════════
# CRUD de Servicios por Trabajadora (gestionado desde el panel)
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def trabajadora_servicios(request, pk):
    """Lista los servicios que ofrece una trabajadora con su duración."""
    from bookings.models import TrabajadoraServicio

    trabajadora = get_object_or_404(Trabajadora, pk=pk)
    servicios = list(
        TrabajadoraServicio.objects.filter(trabajadora=trabajadora)
        .select_related("servicio")
        .order_by("servicio__nombre")
    )
    # Servicios disponibles que aún no tiene asignados
    asignados_ids = [s.servicio_id for s in servicios]
    disponibles = Servicio.objects.filter(activo=True).exclude(pk__in=asignados_ids)

    return render(
        request, "panel/trabajadora_servicios.html",
        {
            "trabajadora": trabajadora,
            "servicios_asignados": servicios,
            "servicios_disponibles": disponibles,
        },
    )


@staff_required
def trabajadora_servicio_add(request, pk):
    """Agrega un nuevo servicio a una trabajadora con duración."""
    from bookings.models import TrabajadoraServicio

    trabajadora = get_object_or_404(Trabajadora, pk=pk)

    if request.method == "POST":
        servicio_id = request.POST.get("servicio")
        duracion = request.POST.get("duracion_minutos")

        if not servicio_id or not duracion:
            messages.error(request, "You must choose a service and a duration.")
            return redirect("panel:trabajadora_servicios", pk=pk)

        try:
            servicio = Servicio.objects.get(pk=servicio_id, activo=True)
            duracion_int = int(duracion)
            if duracion_int < 5:
                raise ValueError("Duration too short")
        except (Servicio.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Invalid data.")
            return redirect("panel:trabajadora_servicios", pk=pk)

        ts, creado = TrabajadoraServicio.objects.get_or_create(
            trabajadora=trabajadora,
            servicio=servicio,
            defaults={"duracion_minutos": duracion_int, "activo": True},
        )
        if not creado:
            messages.warning(
                request,
                f"@{trabajadora.nickname} already had '{servicio.nombre}' assigned.",
            )
        else:
            messages.success(
                request,
                f"✓ '{servicio.nombre}' added to @{trabajadora.nickname} ({duracion_int} min).",
            )
        return redirect("panel:trabajadora_servicios", pk=pk)

    return redirect("panel:trabajadora_servicios", pk=pk)


@staff_required
def trabajadora_servicio_edit(request, ts_pk):
    """Edita la duración de un servicio asignado."""
    from bookings.models import TrabajadoraServicio

    ts = get_object_or_404(TrabajadoraServicio, pk=ts_pk)

    if request.method == "POST":
        duracion = request.POST.get("duracion_minutos")
        try:
            duracion_int = int(duracion)
            if duracion_int < 5:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "Invalid duration (minimum 5 minutes).")
            return redirect("panel:trabajadora_servicios", pk=ts.trabajadora_id)

        ts.duracion_minutos = duracion_int
        ts.save(update_fields=["duracion_minutos"])
        messages.success(
            request,
            f"✓ Duration updated to {duracion_int} min for "
            f"'{ts.servicio.nombre}'.",
        )
        return redirect("panel:trabajadora_servicios", pk=ts.trabajadora_id)

    return render(
        request, "panel/trabajadora_servicio_edit.html",
        {"ts": ts},
    )


@staff_required
@require_POST
def trabajadora_servicio_delete(request, ts_pk):
    from bookings.models import TrabajadoraServicio

    ts = get_object_or_404(TrabajadoraServicio, pk=ts_pk)
    trabajadora_id = ts.trabajadora_id
    nombre = ts.servicio.nombre
    ts.delete()
    messages.warning(
        request,
        f"Removed '{nombre}' from this technician's services.",
    )
    return redirect("panel:trabajadora_servicios", pk=trabajadora_id)


@staff_required
@require_POST
def trabajadora_servicio_toggle(request, ts_pk):
    from bookings.models import TrabajadoraServicio

    ts = get_object_or_404(TrabajadoraServicio, pk=ts_pk)
    ts.activo = not ts.activo
    ts.save(update_fields=["activo"])
    estado = "activated" if ts.activo else "paused"
    messages.info(
        request,
        f"'{ts.servicio.nombre}' {estado} for this technician.",
    )
    return redirect("panel:trabajadora_servicios", pk=ts.trabajadora_id)


# ═════════════════════════════════════════════════════════════════════════
# CRUD de Galería (gestión desde el panel)
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def galeria_list(request):
    """Lista todas las imágenes de la galería con thumbnails."""
    from gallery.models import ImagenGaleria
    from .forms import ImagenGaleriaForm

    imagenes = ImagenGaleria.objects.all().order_by("orden", "-creado")
    activas_count = sum(1 for i in imagenes if i.activa)
    destacadas_count = sum(1 for i in imagenes if i.destacada)

    return render(
        request, "panel/galeria_list.html",
        {
            "imagenes": imagenes,
            "total": imagenes.count(),
            "activas_count": activas_count,
            "destacadas_count": destacadas_count,
        },
    )


@staff_required
def galeria_create(request):
    """Subir una imagen nueva a la galería."""
    from .forms import ImagenGaleriaForm

    if request.method == "POST":
        form = ImagenGaleriaForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(
                request,
                f"✓ Imagen agregada a la galería"
                f"{' (destacada)' if obj.destacada else ''}.",
            )
            return redirect("panel:galeria_list")
        messages.error(request, "Please review the form fields.")
    else:
        form = ImagenGaleriaForm()

    return render(
        request, "panel/galeria_form.html",
        {"form": form, "titulo": "New gallery image", "obj": None},
    )


@staff_required
def galeria_update(request, pk):
    """Editar una imagen existente."""
    from gallery.models import ImagenGaleria
    from .forms import ImagenGaleriaForm

    obj = get_object_or_404(ImagenGaleria, pk=pk)
    if request.method == "POST":
        form = ImagenGaleriaForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Image updated.")
            return redirect("panel:galeria_list")
        messages.error(request, "Please review the form fields.")
    else:
        form = ImagenGaleriaForm(instance=obj)

    return render(
        request, "panel/galeria_form.html",
        {"form": form, "titulo": f"Edit image #{obj.pk}", "obj": obj},
    )


@staff_required
def galeria_delete(request, pk):
    """Eliminar imagen (con confirmación)."""
    from gallery.models import ImagenGaleria

    obj = get_object_or_404(ImagenGaleria, pk=pk)
    if request.method == "POST":
        # Borrar también el archivo físico
        if obj.imagen:
            obj.imagen.delete(save=False)
        obj.delete()
        messages.warning(request, "Image deleted from the gallery.")
        return redirect("panel:galeria_list")

    return render(
        request, "panel/galeria_confirm_delete.html",
        {"obj": obj},
    )


@staff_required
@require_POST
def galeria_toggle(request, pk):
    """Activar/Desactivar visibilidad pública."""
    from gallery.models import ImagenGaleria

    obj = get_object_or_404(ImagenGaleria, pk=pk)
    obj.activa = not obj.activa
    obj.save(update_fields=["activa"])
    estado = "visible" if obj.activa else "hidden"
    messages.info(request, f"Image is now {estado} on the public gallery.")
    return redirect("panel:galeria_list")


@staff_required
@require_POST
def galeria_destacar(request, pk):
    """Marcar/desmarcar como destacada."""
    from gallery.models import ImagenGaleria

    obj = get_object_or_404(ImagenGaleria, pk=pk)
    obj.destacada = not obj.destacada
    obj.save(update_fields=["destacada"])
    estado = "featured ⭐" if obj.destacada else "unfeatured"
    messages.info(request, f"Image marked as {estado}.")
    return redirect("panel:galeria_list")


@staff_required
@require_POST
def galeria_reordenar(request, pk, direccion):
    """Mover una imagen arriba o abajo en el orden."""
    from gallery.models import ImagenGaleria

    obj = get_object_or_404(ImagenGaleria, pk=pk)
    if direccion == "subir":
        # Buscar la imagen anterior (con orden menor o más reciente)
        anterior = (
            ImagenGaleria.objects
            .filter(orden__lt=obj.orden)
            .order_by("-orden", "-creado")
            .first()
        )
        if anterior:
            obj.orden, anterior.orden = anterior.orden, obj.orden
            obj.save(update_fields=["orden"])
            anterior.save(update_fields=["orden"])
        elif obj.orden > 0:
            obj.orden -= 1
            obj.save(update_fields=["orden"])
    elif direccion == "bajar":
        siguiente = (
            ImagenGaleria.objects
            .filter(orden__gt=obj.orden)
            .order_by("orden", "creado")
            .first()
        )
        if siguiente:
            obj.orden, siguiente.orden = siguiente.orden, obj.orden
            obj.save(update_fields=["orden"])
            siguiente.save(update_fields=["orden"])
        else:
            obj.orden += 1
            obj.save(update_fields=["orden"])
    return redirect("panel:galeria_list")


# ═════════════════════════════════════════════════════════════════════════
# CRUD de Servicios (gestión desde el panel)
# ═════════════════════════════════════════════════════════════════════════
@staff_required
def servicio_list(request):
    """Lista todos los servicios + cuántas trabajadoras los ofrecen."""
    from bookings.models import TrabajadoraServicio

    qs = Servicio.objects.all().order_by("orden", "nombre")
    # Para cada servicio, contar cuántas trabajadoras lo ofrecen
    servicios = []
    for s in qs:
        n = TrabajadoraServicio.objects.filter(
            servicio=s, activo=True
        ).count()
        servicios.append({"obj": s, "num_trabajadoras": n})

    return render(
        request, "panel/servicio_list.html",
        {
            "servicios": servicios,
            "total": qs.count(),
            "activos": qs.filter(activo=True).count(),
            "destacados": qs.filter(destacado=True).count(),
        },
    )


@staff_required
def servicio_create(request):
    from .forms import ServicioForm

    if request.method == "POST":
        form = ServicioForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"✓ Service '{obj.nombre}' created.")
            return redirect("panel:servicio_list")
        messages.error(request, "Please review the form fields.")
    else:
        form = ServicioForm()

    return render(
        request, "panel/servicio_form.html",
        {"form": form, "titulo": "New Service", "obj": None},
    )


@staff_required
def servicio_update(request, pk):
    from .forms import ServicioForm

    obj = get_object_or_404(Servicio, pk=pk)
    if request.method == "POST":
        form = ServicioForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "✓ Service updated.")
            return redirect("panel:servicio_list")
        messages.error(request, "Please review the form fields.")
    else:
        form = ServicioForm(instance=obj)

    return render(
        request, "panel/servicio_form.html",
        {"form": form, "titulo": f"Edit '{obj.nombre}'", "obj": obj},
    )


@staff_required
def servicio_delete(request, pk):
    obj = get_object_or_404(Servicio, pk=pk)
    if request.method == "POST":
        nombre = obj.nombre
        obj.delete()
        messages.warning(request, f"Service '{nombre}' deleted.")
        return redirect("panel:servicio_list")
    return render(
        request, "panel/servicio_confirm_delete.html",
        {"obj": obj},
    )


@staff_required
@require_POST
def servicio_toggle(request, pk):
    obj = get_object_or_404(Servicio, pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=["activo"])
    estado = "active" if obj.activo else "paused"
    messages.info(request, f"'{obj.nombre}' is now {estado}.")
    return redirect("panel:servicio_list")


@staff_required
@require_POST
def servicio_destacar(request, pk):
    obj = get_object_or_404(Servicio, pk=pk)
    obj.destacado = not obj.destacado
    obj.save(update_fields=["destacado"])
    estado = "featured ⭐" if obj.destacado else "unfeatured"
    messages.info(request, f"'{obj.nombre}' is now {estado}.")
    return redirect("panel:servicio_list")







# ═════════════════════════════════════════════════════════════════════════
# 📱 WORKERS VIEW — Public read-only weekly calendar (no auth required)
# ═════════════════════════════════════════════════════════════════════════
def workers_calendar(request):
    """
    Public calendar for workers - read-only, mobile-optimized.
    Shows weekly schedule WITHOUT requiring login.
    """
    try:
        offset = int(request.GET.get("w", "0"))
    except ValueError:
        offset = 0

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=offset)
    dias = [inicio_semana + timedelta(days=i) for i in range(7)]

    citas_qs = (
        Cita.objects.filter(fecha__gte=dias[0], fecha__lte=dias[-1])
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("trabajadora", "servicio")
        .order_by("fecha", "hora")
    )

    # Build grid: trabajadora -> {(fecha, hora): cita}
    grid = {}
    for c in citas_qs:
        if c.trabajadora_id is None:
            continue
        grid.setdefault(c.trabajadora, {})[(c.fecha, c.hora)] = c

    return render(
        request, "panel/workers_calendar.html",
        {
            "dias": dias,
            "grid": grid,
            "offset": offset,
            "anterior": offset - 1,
            "siguiente": offset + 1,
            "es_actual": offset == 0,
            "n_total": citas_qs.count(),
        },
    )




# ═════════════════════════════════════════════════════════════════════════
# 👷 WORKER PORTAL — Personal dashboard with login (nickname + password)
# ═════════════════════════════════════════════════════════════════════════

def worker_login(request):
    """Login page for workers using nickname + worker_password."""
    if request.method == "POST":
        nickname = request.POST.get("nickname", "").strip().lower()
        password = request.POST.get("password", "").strip()
        
        try:
            # Find worker by nickname
            worker = Trabajadora.objects.get(nickname=nickname, activa=True)
            
            # Verify password
            if worker.worker_password and worker.worker_password == password:
                # Login successful - store worker ID in session
                request.session['worker_id'] = worker.pk
                request.session['worker_nickname'] = worker.nickname
                messages.success(request, f"Welcome, @{worker.nickname}!")
                return redirect('worker_dashboard')
            else:
                messages.error(request, "Invalid credentials. Please check your password.")
        except Trabajadora.DoesNotExist:
            messages.error(request, "Invalid credentials. Please check your nickname.")
    
    return render(request, 'panel/worker_login.html')


def worker_logout(request):
    """Logout worker."""
    if 'worker_id' in request.session:
        del request.session['worker_id']
        del request.session['worker_nickname']
    messages.info(request, "You have been logged out.")
    return redirect('worker_login')


def worker_required(view_func):
    """Decorator to protect worker views."""
    def wrapper(request, *args, **kwargs):
        if 'worker_id' not in request.session:
            messages.warning(request, "Please log in to continue.")
            return redirect('worker_login')
        try:
            worker = Trabajadora.objects.get(pk=request.session['worker_id'], activa=True)
            request.worker = worker
            return view_func(request, *args, **kwargs)
        except Trabajadora.DoesNotExist:
            del request.session['worker_id']
            messages.error(request, "Your account is no longer active.")
            return redirect('worker_login')
    return wrapper

@worker_required
def worker_dashboard(request):
    """Personal dashboard showing appointments AND income for this worker."""
    worker = request.worker
    
    # ── Appointments (weekly) ────────────────────────────────────────
    try:
        offset = int(request.GET.get("w", "0"))
    except ValueError:
        offset = 0
    
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=offset)
    dias = [inicio_semana + timedelta(days=i) for i in range(7)]
    
    citas_qs = (
        Cita.objects.filter(
            trabajadora=worker,
            fecha__gte=dias[0],
            fecha__lte=dias[-1]
        )
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .select_related("servicio")
        .order_by("fecha", "hora")
    )
    
    # Build grid by day
    grid = {}
    ahora = datetime.now()
    for d in dias:
        grid[d] = []
    
    for c in citas_qs:
        # Check if appointment is in the past
        cita_datetime = datetime.combine(c.fecha, c.hora)
        c.es_pasada = cita_datetime < ahora
        grid[c.fecha].append(c)
    
    # Count by status
    pendientes = citas_qs.filter(estado=Cita.ESTADO_PENDIENTE).count()
    confirmadas = citas_qs.filter(estado=Cita.ESTADO_CONFIRMADA).count()
    completadas = citas_qs.filter(estado=Cita.ESTADO_COMPLETADA).count()
    
    # ── Income Summary (filterable by date) ──────────────────────────
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    
    if fecha_fin_str:
        try:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_fin = date.today()
    else:
        fecha_fin = date.today()
    
    if fecha_inicio_str:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_inicio = fecha_fin - timedelta(days=30)
    else:
        fecha_inicio = fecha_fin - timedelta(days=30)
    
    # Filter registros by selected date range
    registros = (
        Registro.objects.filter(
            trabajadora=worker,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin
        )
        .order_by("-fecha")
    )
    
    # Calculate totals for the filtered period
    agg = registros.aggregate(
        total_servicios=Sum("monto"),
        total_propinas=Sum("propina"),
        total_ganado=Sum("total"),
        num_registros=Count("pk"),
    )
    
    total_servicios = agg["total_servicios"] or Decimal("0")
    total_propinas = agg["total_propinas"] or Decimal("0")
    total_ganado = agg["total_ganado"] or Decimal("0")
    num_registros = agg["num_registros"]
    
    return render(
        request, 'panel/worker_dashboard.html',
        {
            # Appointments
            "worker": worker,
            "dias": dias,
            "grid": grid,
            "offset": offset,
            "anterior": offset - 1,
            "siguiente": offset + 1,
            "es_actual": offset == 0,
            "n_total": citas_qs.count(),
            "pendientes": pendientes,
            "confirmadas": confirmadas,
            "completadas": completadas,
            
            # Income - TOTALS UPDATE WITH FILTER
            "registros": registros,
            "total_servicios": total_servicios,
            "total_propinas": total_propinas,
            "total_ganado": total_ganado,
            "num_registros": num_registros,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
        },
    )

@worker_required
@require_POST
def worker_complete_appointment(request, pk):
    """Mark appointment as completed (only if it belongs to this worker)."""
    worker = request.worker
    cita = get_object_or_404(Cita, pk=pk, trabajadora=worker)
    
    # Check if appointment is in the past
    ahora = datetime.now()
    cita_datetime = datetime.combine(cita.fecha, cita.hora)
    
    if cita_datetime < ahora:
        messages.error(request, "Cannot complete past appointments. This appointment has already passed.")
        return redirect('worker_dashboard')
    
    if cita.estado != Cita.ESTADO_COMPLETADA:
        cita.estado = Cita.ESTADO_COMPLETADA
        # Bypass validation for past dates by using update_fields
        cita.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"✓ Completed: {cita.nombre_cliente}")
    
    return redirect('worker_dashboard')