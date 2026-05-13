/* =========================================================================
   ALAMBRA NAILS · main.js
   - Navbar scroll
   - Mobile nav toggle
   - Smooth scroll for service links (pre-selects service)
   - Reveal on scroll
   - Toasts auto-close
   - AJAX load of available hours based on selected date
   ========================================================================= */
(function () {
  'use strict';

  // ── 1. Navbar: add .scrolled when past 30px ───────────────
  const navbar = document.getElementById('navbar');
  const onScroll = () => {
    if (!navbar) return;
    navbar.classList.toggle('scrolled', window.scrollY > 30);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();


  // ── 2. Mobile nav toggle ────────────────────────────────────────────
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      const open = navLinks.classList.toggle('is-open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
    // When clicking a link, close mobile menu.
    navLinks.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        navLinks.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }


  // ── 3. "Book this service" CTAs: pre-select the service ─
  document.querySelectorAll('.service-cta[data-servicio]').forEach(link => {
    link.addEventListener('click', () => {
      const id = link.dataset.servicio;
      setTimeout(() => {
        const select = document.getElementById('id_servicio');
        if (select) select.value = id;
      }, 50);
    });
  });


  // ── 4. Reveal on scroll using IntersectionObserver ────────────────
  const revealEls = document.querySelectorAll(
    '.service-card, .gallery-item, .value, .contact-card, .section-header'
  );
  revealEls.forEach(el => el.classList.add('reveal'));
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(el => io.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('is-visible'));
  }


  // ── 5. Messages/toasts: auto-close and button ─────────────────────────
  document.querySelectorAll('.message').forEach(msg => {
    const close = msg.querySelector('.message-close');
    const dismiss = () => msg.style.display = 'none';
    if (close) close.addEventListener('click', dismiss);
    setTimeout(dismiss, 8000);
  });


  // ── 6. Booking: update available hours when date changes ─
  const fechaInput = document.getElementById('id_fecha');
  const horaSelect = document.getElementById('id_hora');
  const horaHint = document.getElementById('horaHint');

  function updateAvailableHours() {
    if (!fechaInput || !horaSelect) return;
    const fecha = fechaInput.value;
    if (!fecha) {
      // 🇬🇧 Translated: "Selecciona primero una fecha"
      horaHint && (horaHint.textContent = 'Please select a date first');
      return;
    }
    // 🇬🇧 Translated: "Cargando disponibilidad…"
    horaHint && (horaHint.textContent = 'Loading availability…');
    fetch(`/reservar/horas-disponibles/?fecha=${encodeURIComponent(fecha)}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(r => {
        // 🇬🇧 Translated error message
        if (!r.ok) throw new Error('Error checking availability');
        return r.json();
      })
      .then(data => {
        const ocupadas = new Set(data.ocupadas || []);
        const valorActual = horaSelect.value;
        let primeraDisponible = '';

        Array.from(horaSelect.options).forEach(opt => {
          if (!opt.value) return;
          // Options come as '09:00:00' or '09:00'; normalize.
          const val = opt.value.length >= 5 ? opt.value.substring(0, 5) : opt.value;
          if (ocupadas.has(val)) {
            opt.disabled = true;
            if (!opt.textContent.includes('(occupied)')) {
              opt.textContent = opt.textContent.replace(/\s*\(ocupado\)$/, '') + ' (occupied)';
            }
          } else {
            opt.disabled = false;
            opt.textContent = opt.textContent.replace(/\s*\(ocupado\)$/, '');
            if (!primeraDisponible) primeraDisponible = opt.value;
          }
        });

        // If selected option became occupied, clear it.
        if (horaSelect.value && horaSelect.options[horaSelect.selectedIndex]?.disabled) {
          horaSelect.value = '';
        }

        if (horaHint) {
          // 🇬🇧 Translated availability messages
          horaHint.textContent = ocupadas.size
            ? `${ocupadas.size} time slot(s) already occupied that day`
            : 'All time slots available ✨';
        }
      })
      .catch(err => {
        console.error(err);
        // 🇬🇧 Translated: "No pudimos cargar la disponibilidad"
        horaHint && (horaHint.textContent = 'We could not load availability');
      });
  }
  if (fechaInput) {
    fechaInput.addEventListener('change', updateAvailableHours);
    if (fechaInput.value) updateAvailableHours();
  }


  // ── 7. If returning from successful booking, scroll to contact ───────
  if (window.__alambraReservaOk) {
    setTimeout(() => {
      const target = document.getElementById('contacto');
      if (target) target.scrollIntoView({ behavior: 'smooth' });
    }, 300);
  }


  // ── 8. Light frontend form validation ───────────────────
  const form = document.getElementById('bookingForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      const required = form.querySelectorAll('[required], #id_nombre_cliente, #id_telefono, #id_servicio, #id_fecha, #id_hora');
      let firstInvalid = null;
      required.forEach(input => {
        if (!input.value || (input.tagName === 'SELECT' && !input.value)) {
          input.setAttribute('aria-invalid', 'true');
          if (!firstInvalid) firstInvalid = input;
        } else {
          input.removeAttribute('aria-invalid');
        }
      });
      if (firstInvalid) {
        e.preventDefault();
        firstInvalid.focus();
      }
    });
  }
})();