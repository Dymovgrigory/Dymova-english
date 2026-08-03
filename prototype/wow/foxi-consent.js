/* Foxinburg cookie-consent (сессия 46).
   Показывает баннер согласия на cookie, выбор хранит в localStorage
   (ключ fxb_cookie_consent_v1) и рассылает событие 'fxb-consent'
   (document, detail: {v: 'accept'|'decline'}) — задел для будущего
   гейтинга аналитики/пикселей по согласию. window.FXBConsent.get()
   возвращает сохранённый выбор или null. */
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
    box.setAttribute("aria-label", "Согласие на использование cookie");
    box.innerHTML =
      '<p class="fxb-consent-text">Мы используем cookie, чтобы сайт работал стабильно, ' +
      "а мы могли понимать, что интересно посетителям, и делать школу лучше. " +
      'Подробнее — в <a href="/policy" target="_blank" rel="noopener">политике конфиденциальности</a>.</p>' +
      '<div class="fxb-consent-btns">' +
      '<button type="button" class="fxb-consent-btn fxb-consent-accept">Принять</button>' +
      '<button type="button" class="fxb-consent-btn fxb-consent-decline">Отклонить</button>' +
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
