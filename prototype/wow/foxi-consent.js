/* Foxinburg cookie-consent (сессия 46, текст пересмотрен 14.09.2026).
   Показывает баннер, выбор хранит в localStorage (ключ
   fxb_cookie_consent_v1 — тот же ключ читает foxi-analytics.js) и
   рассылает событие 'fxb-consent' (document, detail: {v:
   'accept'|'decline'}). window.FXBConsent.get() возвращает сохранённый
   выбор или null.

   Чем управляет выбор: НЕ фактом сбора статистики (обезличенная Метрика
   работает всегда — так же, как это описано в /policy), а расширенной
   аналитикой: вебвизором, картой кликов и GA4. Раскладка и причины —
   в шапке foxi-analytics.js. */
(function () {
  var KEY = "fxb_cookie_consent_v1";

  function get() {
    try {
      var raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  window.FXBConsent = { get: get };

  function announce(v) {
    try {
      document.dispatchEvent(new CustomEvent("fxb-consent", { detail: { v: v } }));
    } catch (e) {}
  }

  var saved = get();
  if (saved && saved.v) {
    // Согласие уже дано ранее — просто уведомляем подписчиков (будущая аналитика).
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { announce(saved.v); });
    } else {
      announce(saved.v);
    }
    return;
  }

  function build() {
    var box = document.createElement("div");
    box.id = "fxb-consent";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-live", "polite");
    box.setAttribute("aria-label", "Cookie и аналитика");
    // Текст информирующий, а не выпрашивающий разрешение: обезличенная
    // статистика собирается всегда (так и записано в /policy), а кнопки
    // управляют именно расширенной аналитикой — вебвизором, картой кликов
    // и GA4. Называем это прямо, чтобы баннер не обещал того, чего не делает.
    box.innerHTML =
      '<p class="fxb-consent-text">Сайт собирает обезличенную статистику посещений — ' +
      "так мы понимаем, что интересно посетителям. Если разрешите расширенную аналитику, " +
      "мы сможем видеть, как вы пользуетесь страницами, и быстрее чинить неудобства. " +
      'Подробнее — в <a href="/policy" target="_blank" rel="noopener">политике конфиденциальности</a>.</p>' +
      '<div class="fxb-consent-btns">' +
      '<button type="button" class="fxb-consent-btn fxb-consent-accept">Разрешить</button>' +
      '<button type="button" class="fxb-consent-btn fxb-consent-decline">Только необходимое</button>' +
      "</div>";
    document.body.appendChild(box);
    requestAnimationFrame(function () {
      box.classList.add("fxb-consent-show");
    });

    function choose(v) {
      try {
        localStorage.setItem(KEY, JSON.stringify({ v: v, t: Date.now() }));
      } catch (e) {}
      announce(v);
      box.classList.remove("fxb-consent-show");
      box.classList.add("fxb-consent-hide");
      setTimeout(function () {
        if (box.parentNode) box.parentNode.removeChild(box);
      }, 400);
    }

    box.querySelector(".fxb-consent-accept").addEventListener("click", function () { choose("accept"); });
    box.querySelector(".fxb-consent-decline").addEventListener("click", function () { choose("decline"); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
