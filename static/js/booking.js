/**
 * booking.js — availability calendar for public booking flow.
 *
 * Globals injected by template:
 *   NICKNAME           → technician nickname
 *   DIAS_CON_HORARIO   → array of numbers 0..6 (Monday=0) with active days
 *   HOY_ISO            → "YYYY-MM-DD" of current server day
 *   VENTANA_DIAS       → how many days in the future booking is allowed
 *   SLOTS_URL          → endpoint to fetch slots
 *   CONFIRM_URL_TPL    → URL template with __FECHA__ and __HORA__ to replace
 */
(function () {
  "use strict";

  // 🇬🇧 Month names translated to English
  const MES_NOMBRES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  // Converts "YYYY-MM-DD" to local Date (no timezone issues).
  function parseISO(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  function fmtISO(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }
  // Monday = 0 instead of Sunday
  function weekdayLunes(date) {
    return (date.getDay() + 6) % 7;
  }

  const HOY = parseISO(HOY_ISO);
  const TOPE = new Date(HOY);
  TOPE.setDate(TOPE.getDate() + VENTANA_DIAS);

  let currentMonth = new Date(HOY.getFullYear(), HOY.getMonth(), 1);
  let selectedDate = null;

  const $monthLabel = document.getElementById("calMonthLabel");
  const $days = document.getElementById("calDays");
  const $prev = document.getElementById("calPrev");
  const $next = document.getElementById("calNext");
  const $slotsTitle = document.getElementById("slotsTitle");
  const $slotsHint = document.getElementById("slotsHint");
  const $slotsGrid = document.getElementById("slotsGrid");

  function renderMonth() {
    const y = currentMonth.getFullYear();
    const m = currentMonth.getMonth();
    $monthLabel.textContent = `${MES_NOMBRES[m]} ${y}`;

    $days.innerHTML = "";

    // Day of week for the 1st (Monday-based)
    const primerDia = new Date(y, m, 1);
    const offsetInicio = weekdayLunes(primerDia);
    const diasEnMes = new Date(y, m + 1, 0).getDate();

    // Start padding (days from previous month, in gray)
    for (let i = 0; i < offsetInicio; i++) {
      const cell = document.createElement("button");
      cell.className = "cal-day is-other-month";
      cell.disabled = true;
      cell.textContent = "";
      $days.appendChild(cell);
    }

    for (let d = 1; d <= diasEnMes; d++) {
      const fecha = new Date(y, m, d);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cal-day";
      cell.textContent = d;

      const esHoy = fmtISO(fecha) === HOY_ISO;
      const esPasado = fecha < HOY && !esHoy;
      const fueraVentana = fecha > TOPE;
      const diaSemana = weekdayLunes(fecha);
      const tieneHorario = DIAS_CON_HORARIO.indexOf(diaSemana) !== -1;

      if (esPasado || fueraVentana || !tieneHorario) {
        cell.disabled = true;
      } else {
        cell.classList.add("is-available");
        cell.dataset.fecha = fmtISO(fecha);
        cell.addEventListener("click", () => seleccionarFecha(cell));
      }
      if (esHoy) cell.classList.add("is-today");
      if (selectedDate && fmtISO(fecha) === selectedDate) {
        cell.classList.add("is-selected");
      }

      $days.appendChild(cell);
    }
  }

  function seleccionarFecha(cell) {
    // Remove previous selection
    document.querySelectorAll(".cal-day.is-selected").forEach(el => {
      el.classList.remove("is-selected");
    });
    cell.classList.add("is-selected");

    selectedDate = cell.dataset.fecha;
    cargarSlots(selectedDate);
  }

  function cargarSlots(fechaIso) {
    // 🇬🇧 Changed locale to en-US for English date format
    const fechaLegible = parseISO(fechaIso).toLocaleDateString("en-US", {
      weekday: "long", day: "numeric", month: "long"
    });
    // 🇬🇧 Translated: "Horarios del" → "Available times for"
    $slotsTitle.textContent = `Available times for ${fechaLegible}`;
    // 🇬🇧 Translated: "Cargando…" → "Loading…"
    $slotsHint.textContent = "Loading…";
    $slotsGrid.innerHTML = "";

    let url = `${SLOTS_URL}?fecha=${fechaIso}&_t=${Date.now()}`;
    if (window.SERVICIO_ID) {
      url += `&servicio=${window.SERVICIO_ID}`;
    }
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(data => {
        const slots = data.slots || [];
        if (slots.length === 0) {
          // 🇬🇧 Translated message
          $slotsHint.textContent = "No available time slots for this day. Try another date.";
          return;
        }
        // 🇬🇧 Translated: "horario(s) disponible(s) — toca uno para reservar:"
        $slotsHint.textContent = `${slots.length} time slot(s) available — tap one to book:`;
        slots.forEach(hhmm => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "slot-btn";
          btn.textContent = hhmm;
          btn.addEventListener("click", () => irAConfirmar(fechaIso, hhmm));
          $slotsGrid.appendChild(btn);
        });
      })
      .catch(() => {
        // 🇬🇧 Translated error message
        $slotsHint.textContent = "Error loading time slots. Please reload the page.";
      });
  }

  // Allows service selector to force reload.
  window.RECARGAR_SLOTS = function () {
    if (selectedDate) cargarSlots(selectedDate);
  };

  function irAConfirmar(fechaIso, hhmm) {
    const horaUrl = hhmm.replace(":", "-");
    let url = CONFIRM_URL_TPL
      .replace("__FECHA__", fechaIso)
      .replace("__HORA__", horaUrl);
    if (window.SERVICIO_ID) {
      url += `?servicio=${window.SERVICIO_ID}`;
    }
    window.location.href = url;
  }

  $prev.addEventListener("click", () => {
    currentMonth.setMonth(currentMonth.getMonth() - 1);
    // Do not go back beyond current month
    if (currentMonth < new Date(HOY.getFullYear(), HOY.getMonth(), 1)) {
      currentMonth = new Date(HOY.getFullYear(), HOY.getMonth(), 1);
    }
    renderMonth();
  });
  $next.addEventListener("click", () => {
    currentMonth.setMonth(currentMonth.getMonth() + 1);
    // Do not advance beyond limit (booking window)
    const topeMes = new Date(TOPE.getFullYear(), TOPE.getMonth(), 1);
    if (currentMonth > topeMes) {
      currentMonth = topeMes;
    }
    renderMonth();
  });

  renderMonth();
})();