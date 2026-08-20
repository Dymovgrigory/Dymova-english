/* Foxinburg analytics loader (сессия 59, SEO P0).
   Гейтинг по согласию: счётчики подключаются ТОЛЬКО после события
   'fxb-consent' с detail.v === 'accept' (см. foxi-consent.js).
   Если пользователь отклонил — аналитика не грузится вообще.
   Подключает:
   - Яндекс.Метрику 109945462 (вебвизор, карта кликов, точный показатель
     отказов) — цели 578168283/578168629/578168992/578169121 настроены
     в кабинете и начинают работать автоматически.
   - GA4 G-9XMYR6MJGL.
   Без <noscript>-пикселя: он не может быть согласован по 152-ФЗ. */
(function () {
  var YM_ID = 109945462;
  var GA_ID = "G-9XMYR6MJGL";
  var loaded = false;

  function loadMetrika() {
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) { return; }
      }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0];
      k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
    ym(YM_ID, "init", {
      clickmap: true,
      trackLinks: true,
      accurateTrackBounce: true,
      webvisor: true,
      defer: true
    });
  }

  function loadGA4() {
    var s = document.createElement("script");
    s.async = 1;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", GA_ID);
  }

  function onConsent(e) {
    if (loaded) { return; }
    if (!e || !e.detail || e.detail.v !== "accept") { return; }
    loaded = true;
    try { loadMetrika(); } catch (err) {}
    try { loadGA4(); } catch (err) {}
  }

  document.addEventListener("fxb-consent", onConsent);
})();
