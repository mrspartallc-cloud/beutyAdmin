# Alambra Nails — Sistema de citas
El sistema vale de 3000$ a 5000$ se lo ofrezco en 3000$ para ti

mensual 497 la primera instalacion 
y 50 mensulidad 


"Por menos de lo que cuesta una clienta nueva al mes ($30-50), tienes un sistema que evita pérdidas por errores, ahorra 5-10 horas semanales de administración y te da reportes claros para tomar decisiones. ¿Empezamos con el setup esta semana?"



Sitio web + back-office en Django 6 para un salón de uñas. Incluye:

- 🌸 **Landing pública** con servicios, galería, equipo y CTA a reserva
- 📅 **Sistema de citas** privado-por-nickname, con calendario dinámico
- 🔒 **Privacidad**: clientes solo ven el nickname, NUNCA el nombre real
- 👩‍💼 **Panel para trabajadoras** que gestionan sus propias citas
- 🛠 **Panel admin** con métricas, calendario semanal y detección de colisiones
- 💵 Todo en formato **US** (teléfonos +1, dólares, horario en inglés)

## ⚙️ Setup

```bash
# 1. Crear venv e instalar deps
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Migraciones (ESTO ES IMPORTANTE — modelos cambiaron mucho)
python manage.py makemigrations panel bookings core gallery
python manage.py migrate

# 3. Superusuario
python manage.py createsuperuser

# 4. Correr
python manage.py runserver
```

Sitio en `http://127.0.0.1:8000/` · Admin en `/admin/` · Panel en `/panel/`.

## 🗺 Mapa de URLs

### Público
| URL | Qué hace |
|---|---|
| `/` | Landing |
| `/reservar/` | Catálogo de trabajadoras (busca por nickname) |
| `/reservar/<nickname>/` | Perfil + calendario de disponibilidad |
| `/reservar/<nickname>/<fecha>/<hora>/` | Form de confirmación |
| `/reservar/exito/<id>/` | Página de éxito |

### Panel (login en `/panel/login/`)

**Staff (administrador)** — al loguear va a `/panel/`:
| URL | Qué hace |
|---|---|
| `/panel/` | Dashboard con métricas + ingresos |
| `/panel/citas/` | Tabla de TODAS las citas con filtros |
| `/panel/calendario/` | Calendario semanal con detección de colisiones |
| `/panel/trabajadoras/` | CRUD de trabajadoras |
| `/panel/ingresos/nuevo/` | Registrar ingreso |
| `/panel/resumen/` | Reporte financiero |

**Trabajadora** — al loguear va a `/panel/mis-citas/`:
| URL | Qué hace |
|---|---|
| `/panel/mis-citas/` | Sus citas (aceptar / rechazar / completar) |
| `/panel/mi-disponibilidad/` | Configurar sus horarios semanales |

## 👥 Cómo crear una trabajadora con login propio

1. Ve a `/admin/auth/user/` y crea un usuario (sin marcar `is_staff`).
2. Ve a `/admin/panel/trabajadora/` (o `/panel/trabajadoras/nueva/`) y crea la trabajadora.
3. En el campo "Usuario para login (opcional)" elige el usuario que creaste.
4. Asegúrate de que el `nickname` sea legible (ej. `mara-fit`). Si lo dejas vacío se autogenera.
5. La trabajadora ya puede entrar en `/panel/login/` con sus credenciales.
6. Lo primero que debe hacer es ir a **Mi disponibilidad** y agregar al menos un bloque, para que aparezca en el catálogo público.

## 🔒 Privacidad — qué ven los clientes

| Campo | ¿Lo ve el cliente? |
|---|---|
| `nickname` | ✅ Sí (es lo único que se muestra) |
| `bio`, `foto` | ✅ Sí (si están definidos) |
| `nombre_completo` | ❌ Nunca |
| `correo`, `telefono`, `porcentaje` | ❌ Nunca |

Las vistas públicas (`bookings/views.py`) **siempre** filtran por `nickname`, jamás por `id` ni por nombre. Los templates públicos solo renderizan campos públicos.

## 🛡 Cómo se evitan las dobles reservas

Tres capas de defensa:

1. **Constraint en BD** (`UniqueConstraint` con condición `Q(estado != 'cancelada') & Q(trabajadora__isnull=False)`) — previene race conditions a nivel motor.
2. **`Cita.clean()`** — valida en cada `save()` que no haya conflicto y que el slot caiga dentro de un `HorarioDisponible`.
3. **`bookings.views.confirmar_cita`** — antes de mostrar el form, re-verifica que el slot siga libre. Si se tomó mientras el cliente decidía, redirige a `slot_taken.html`.

## 📞 Formato de teléfono US

Validador regex: `^\+?1?[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}$`

Acepta: `+1 (555) 123-4567`, `555-123-4567`, `5551234567`, `1.555.123.4567`.

## 🧱 Stack

- **Django 6** (requiere Python 3.12+)
- **SQLite** por defecto (PostgreSQL opcional via env)
- **Pillow** para fotos de trabajadoras y galería
- **DataTables** + jQuery (CDN) para tablas del panel
- **Vanilla JS** para el calendario (sin frameworks)

## ⚠️ Notas de migración desde versión anterior

Los modelos `panel.Trabajadora` y `bookings.Cita` cambiaron significativamente. **Borra `db.sqlite3`** o ejecuta migraciones en orden. Si tenías citas viejas, su campo `trabajadora` quedará en `NULL` (es nullable).

Para regenerar nicknames de trabajadoras existentes:
```bash
python manage.py shell -c "from panel.models import Trabajadora; [t.save() for t in Trabajadora.objects.all()]"
```
# beutyAdmin
