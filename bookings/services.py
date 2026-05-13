"""
Capa de servicios para cálculo de disponibilidad real.

Este módulo encapsula TODA la lógica de:
- Qué trabajadoras pueden hacer un servicio
- Quiénes están laborando un día dado
- Qué huecos libres tienen
- Qué slots ofrecer al cliente, considerando duración variable

Reglas que respeta:
1. Cada trabajadora atiende UNA cita a la vez (no solapamientos).
2. Capacidad simultánea = nº de trabajadoras laborando ese día.
3. Duración del slot depende de (trabajadora, servicio).
4. Cancelled citas no cuentan.
5. Slots dinámicos cada `STEP_MINUTES` (granularidad de búsqueda).
"""
from datetime import date, datetime, time, timedelta

from django.db.models import Prefetch

from .models import (
    Cita, HorarioDisponible, TrabajadoraServicio,
)


# Granularidad para escanear el día en busca de huecos. 15 min es razonable:
# pequeño suficiente para dar opciones flexibles, grande suficiente para no
# saturar visualmente al cliente.
STEP_MINUTES = 15


# ─────────────────────────────────────────────────────────────────────────
# Utilidades de tiempo
# ─────────────────────────────────────────────────────────────────────────
def _to_minutes(t):
    """time(9, 30) → 570."""
    if t is None:
        return None
    return t.hour * 60 + t.minute


def _from_minutes(m):
    """570 → time(9, 30)."""
    return time(m // 60, m % 60)


def _intervalos_libres(bloque_ini, bloque_fin, ocupados):
    """Dado un bloque (ini, fin) y lista de (ini, fin) ocupados,
    devuelve la lista de huecos libres como tuplas (ini, fin).
    Todos los valores en minutos del día.
    """
    if not ocupados:
        return [(bloque_ini, bloque_fin)]

    ocupados = sorted(ocupados, key=lambda x: x[0])
    huecos = []
    cursor = bloque_ini
    for o_ini, o_fin in ocupados:
        # Recortar al bloque
        o_ini = max(o_ini, bloque_ini)
        o_fin = min(o_fin, bloque_fin)
        if o_ini >= bloque_fin:
            break
        if o_fin <= cursor:
            continue
        if o_ini > cursor:
            huecos.append((cursor, o_ini))
        cursor = max(cursor, o_fin)
    if cursor < bloque_fin:
        huecos.append((cursor, bloque_fin))
    return huecos


# ─────────────────────────────────────────────────────────────────────────
# Trabajadoras que pueden hacer X servicio
# ─────────────────────────────────────────────────────────────────────────
def trabajadoras_para_servicio(servicio_id):
    """Trabajadoras activas que tienen TrabajadoraServicio para ese servicio."""
    from panel.models import Trabajadora
    return (
        Trabajadora.objects
        .filter(
            activa=True,
            servicios_que_realiza__servicio_id=servicio_id,
            servicios_que_realiza__activo=True,
        )
        .exclude(nickname__isnull=True)
        .distinct()
    )


def duracion_para(trabajadora_id, servicio_id):
    """Duración personalizada (trabajadora, servicio). None si no existe."""
    ts = TrabajadoraServicio.objects.filter(
        trabajadora_id=trabajadora_id,
        servicio_id=servicio_id,
        activo=True,
    ).first()
    return ts.duracion_minutos if ts else None


# ─────────────────────────────────────────────────────────────────────────
# Huecos libres POR TRABAJADORA en un día dado
# ─────────────────────────────────────────────────────────────────────────
def huecos_libres_trabajadora(trabajadora, fecha):
    """Devuelve lista de tuplas (ini, fin) en minutos del día,
    representando huecos libres de la trabajadora ese día.

    Combina sus bloques de HorarioDisponible activos para ese day-of-week
    y resta sus citas activas (no canceladas) que ocupan rangos de tiempo.
    """
    dia = fecha.weekday()

    bloques = list(
        HorarioDisponible.objects.filter(
            trabajadora=trabajadora, dia_semana=dia, activo=True,
        ).values_list("hora_inicio", "hora_fin")
    )
    if not bloques:
        return []

    # Citas que ocupan rango de tiempo
    citas = list(
        Cita.objects.filter(trabajadora=trabajadora, fecha=fecha)
        .exclude(estado=Cita.ESTADO_CANCELADA)
        .values_list("hora", "duracion_minutos")
    )
    ocupados = []
    for hora, dur in citas:
        ini = _to_minutes(hora)
        ocupados.append((ini, ini + (dur or 60)))

    huecos = []
    for hi, hf in bloques:
        bi = _to_minutes(hi)
        bf = _to_minutes(hf)
        huecos.extend(_intervalos_libres(bi, bf, ocupados))
    return huecos


# ─────────────────────────────────────────────────────────────────────────
# Slots disponibles para un servicio y fecha (todos los recursos)
# ─────────────────────────────────────────────────────────────────────────
def slots_disponibles_servicio(servicio_id, fecha):
    """Lista de slots para un servicio en una fecha.

    Devuelve: [
        {
            "hora": "09:00",
            "trabajadora_id": 4,
            "trabajadora_nick": "mari",
            "duracion": 60,
        },
        ...
    ]
    Ordenado por hora_inicio. Permite slots simultáneos en distintas
    trabajadoras (ese es el truco de la "capacidad real").
    """
    workers = list(trabajadoras_para_servicio(servicio_id))
    if not workers:
        return []

    # Mapa trabajadora_id → duracion_minutos para este servicio
    duraciones = {
        ts["trabajadora_id"]: ts["duracion_minutos"]
        for ts in TrabajadoraServicio.objects.filter(
            servicio_id=servicio_id, activo=True,
            trabajadora__in=workers,
        ).values("trabajadora_id", "duracion_minutos")
    }

    # Filtrar slots pasados si fecha es hoy
    es_hoy = fecha == date.today()
    ahora_min = _to_minutes(datetime.now().time()) if es_hoy else 0

    slots = []
    for w in workers:
        dur = duraciones.get(w.pk)
        if not dur:
            continue
        huecos = huecos_libres_trabajadora(w, fecha)
        for h_ini, h_fin in huecos:
            if h_fin - h_ini < dur:
                continue
            # Generar candidatos cada STEP_MINUTES
            cursor = h_ini
            ultimo_inicio = h_fin - dur
            while cursor <= ultimo_inicio:
                if cursor >= ahora_min:
                    slots.append({
                        "hora": _from_minutes(cursor).strftime("%H:%M"),
                        "hora_minutos": cursor,
                        "trabajadora_id": w.pk,
                        "trabajadora_nick": w.nickname,
                        "duracion": dur,
                    })
                cursor += STEP_MINUTES

    # Ordenar y deduplicar por (hora, trabajadora) - aunque no debería haber
    # duplicados, por seguridad
    slots.sort(key=lambda s: (s["hora_minutos"], s["trabajadora_id"]))
    return slots


def slots_unicos_por_hora(servicio_id, fecha):
    """Variante "agregada": para cada hora donde HAY al menos una trabajadora
    libre, devuelve UNA fila con la lista de candidatas. Útil para
    "cualquier técnica" en flujo público.

    Devuelve: [
        {
            "hora": "09:00",
            "candidatas": [
                {"id": 4, "nick": "mari", "duracion": 60},
                {"id": 5, "nick": "antonia", "duracion": 35},
            ]
        },
        ...
    ]
    """
    crudo = slots_disponibles_servicio(servicio_id, fecha)
    por_hora = {}
    for s in crudo:
        por_hora.setdefault(s["hora"], []).append({
            "id": s["trabajadora_id"],
            "nick": s["trabajadora_nick"],
            "duracion": s["duracion"],
        })
    return [
        {"hora": h, "candidatas": cand}
        for h, cand in sorted(por_hora.items())
    ]


# ─────────────────────────────────────────────────────────────────────────
# Asignación inteligente
# ─────────────────────────────────────────────────────────────────────────
def elegir_trabajadora_libre(servicio_id, fecha, hora):
    """Para un (servicio, fecha, hora), elige la trabajadora con menos carga
    ese día que esté libre y haga el servicio. Devuelve None si nadie.
    """
    from panel.models import Trabajadora

    workers = list(trabajadoras_para_servicio(servicio_id))
    if not workers:
        return None

    duraciones = {
        ts.trabajadora_id: ts.duracion_minutos
        for ts in TrabajadoraServicio.objects.filter(
            servicio_id=servicio_id, activo=True, trabajadora__in=workers,
        )
    }

    candidatas = []
    inicio_min = _to_minutes(hora)
    for w in workers:
        dur = duraciones.get(w.pk)
        if not dur:
            continue
        # Verifica que el rango [inicio, inicio+dur] esté completamente
        # dentro de algún hueco libre.
        fin_min = inicio_min + dur
        for h_ini, h_fin in huecos_libres_trabajadora(w, fecha):
            if h_ini <= inicio_min and h_fin >= fin_min:
                candidatas.append(w)
                break

    if not candidatas:
        return None

    # Ordenar por nº de citas activas ese día (la menos cargada primero)
    def _carga(w):
        return Cita.objects.filter(
            trabajadora=w, fecha=fecha,
        ).exclude(estado=Cita.ESTADO_CANCELADA).count()

    candidatas.sort(key=_carga)
    return candidatas[0]


# ─────────────────────────────────────────────────────────────────────────
# Compatibilidad con código existente que pide slots por trabajadora
# ─────────────────────────────────────────────────────────────────────────
def slots_disponibles_trabajadora(trabajadora, fecha, servicio_id=None):
    """Slots libres de UNA trabajadora en una fecha.

    Si se pasa servicio_id, usa la duración de TrabajadoraServicio.
    Si no, usa SLOT_MINUTES (60) como duración mínima genérica.
    """
    duracion = 60
    if servicio_id:
        d = duracion_para(trabajadora.pk, servicio_id)
        if d:
            duracion = d
        else:
            return []  # no ofrece ese servicio

    es_hoy = fecha == date.today()
    ahora_min = _to_minutes(datetime.now().time()) if es_hoy else 0

    slots = []
    for h_ini, h_fin in huecos_libres_trabajadora(trabajadora, fecha):
        if h_fin - h_ini < duracion:
            continue
        cursor = h_ini
        ultimo_inicio = h_fin - duracion
        while cursor <= ultimo_inicio:
            if cursor >= ahora_min:
                slots.append(_from_minutes(cursor))
            cursor += STEP_MINUTES
    return slots
