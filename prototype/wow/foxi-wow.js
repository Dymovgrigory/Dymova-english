/* Фокси WOW — scroll-эффекты для всех страниц dymova-english.ru.
   Лёгкий (<10 КБ): reveal-анимации, магнитные кнопки, 3D-tilt карточек,
   параллакс декора, ленивая загрузка 3D-маскота после load+idle.
   Уважает prefers-reduced-motion и слабые устройства. */

(() => {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = window.matchMedia('(pointer: fine)').matches;
  const weakDevice =
    (navigator.hardwareConcurrency && navigator.hardwareConcurrency < 4) ||
    (navigator.connection && navigator.connection.saveData);

  /* ---------- 1. Scroll-reveal (IntersectionObserver, once) ---------- */
  const REVEAL_SELECTORS = [
    '#fxb-adv .fxb-card', '#fxb-dir .fxb-card', '#fxb-team .fxb-card',
    '#fxb-reviews .fxb-card', '#fxb-pricing .fxb-card', '#fxb-lang .fxb-card',
    '.fxb-faq details', '.fxb-steps .fxb-step',
    '.fxb-h2', 'h2',
  ];

  function initReveal() {
    if (reduceMotion) return;
    const seen = new Set();
    const targets = [];
    for (const sel of REVEAL_SELECTORS) {
      document.querySelectorAll(sel).forEach((n) => {
        if (!seen.has(n)) { seen.add(n); targets.push(n); }
      });
    }
    if (!targets.length) return;

    // stagger: задержка по позиции элемента внутри родителя
    targets.forEach((n) => {
      n.classList.add('wow-reveal');
      const idx = Array.prototype.indexOf.call(n.parentNode.children, n);
      n.style.transitionDelay = Math.min(idx, 6) * 70 + 'ms';
    });

    const io = new IntersectionObserver((entries) => {
      for (const en of entries) {
        if (en.isIntersecting) {
          en.target.classList.add('is-in');
          io.unobserve(en.target);
        }
      }
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    targets.forEach((n) => io.observe(n));
  }

  /* ---------- 2. Магнитные CTA-кнопки (приём Magnet из motionsites) ---------- */
  function initMagnets() {
    if (reduceMotion || !finePointer) return;
    const STRENGTH = 3, RADIUS = 60;
    document.querySelectorAll('.fxb-btn-main, .fxb-btn, [data-fxb-zayavka]').forEach((btn) => {
      if (btn.closest('.fxb-modal')) return; // кнопки внутри модалок не трогаем
      btn.classList.add('wow-magnet');
      let raf = 0;
      btn.addEventListener('pointermove', (e) => {
        const r = btn.getBoundingClientRect();
        const dx = e.clientX - (r.left + r.width / 2);
        const dy = e.clientY - (r.top + r.height / 2);
        if (Math.hypot(dx, dy) > Math.max(r.width, r.height) / 2 + RADIUS) return;
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          btn.style.transition = 'transform .2s ease-out';
          btn.style.transform = `translate3d(${dx / STRENGTH}px, ${dy / STRENGTH}px, 0)`;
        });
      });
      btn.addEventListener('pointerleave', () => {
        cancelAnimationFrame(raf);
        btn.style.transition = 'transform .5s cubic-bezier(.22,1.4,.36,1)';
        btn.style.transform = '';
      });
    });
  }

  /* ---------- 3. 3D-tilt карточек при наведении ---------- */
  function initTilt() {
    if (reduceMotion || !finePointer) return;
    document.querySelectorAll('#fxb-dir .fxb-card, #fxb-team .fxb-card, #fxb-adv .fxb-card').forEach((card) => {
      card.classList.add('wow-tilt');
      let raf = 0;
      card.addEventListener('pointermove', (e) => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          card.style.transform =
            `perspective(900px) rotateY(${px * 7}deg) rotateX(${-py * 7}deg) translateY(-3px)`;
          card.style.setProperty('--glare-x', (px + 0.5) * 100 + '%');
          card.style.setProperty('--glare-y', (py + 0.5) * 100 + '%');
        });
      });
      card.addEventListener('pointerleave', () => {
        cancelAnimationFrame(raf);
        card.style.transform = '';
      });
    });
  }

  /* ---------- 4. Параллакс декора hero (главная) ---------- */
  function initParallax() {
    if (reduceMotion) return;
    const decors = document.querySelectorAll('#fxb-hero .fxb-hero-decor');
    if (!decors.length) return;
    const speeds = [0.18, -0.12, 0.09];
    decors.forEach((d) => { d.style.willChange = 'transform'; });
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (y < window.innerHeight * 1.5) {
          decors.forEach((d, i) => {
            d.style.transform = `translate3d(0, ${y * speeds[i % speeds.length]}px, 0)`;
          });
        }
        ticking = false;
      });
    }, { passive: true });
  }

  /* ---------- 5. Входная анимация заголовка hero (главная) ---------- */
  function initHero() {
    if (reduceMotion) return;
    const h1 = document.querySelector('#fxb-hero .fxb-slogan-text');
    if (h1) h1.classList.add('wow-hero-in');
  }

  /* ---------- 6. Ленивая загрузка 3D-маскота ---------- */
  function initFoxiLazy() {
    if (reduceMotion || weakDevice) return;
    const start = () => {
      const idle = window.requestIdleCallback || ((cb) => setTimeout(cb, 400));
      idle(() => {
        import('./foxi-3d.js').then((m) => m.initFoxi3D()).catch(() => { /* 3D опционален */ });
      });
    };
    if (document.readyState === 'complete') start();
    else window.addEventListener('load', start, { once: true });
  }

  function boot() {
    initReveal();
    initMagnets();
    initTilt();
    initParallax();
    initHero();
    initFoxiLazy();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
