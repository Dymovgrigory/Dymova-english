/* Foxinburg analytics loader (сессия 59, пересмотрен 14.09.2026,
   фикс 17.09.2026: CS_ERR_UNKNOWN / низкая активность счётчика).

   Два уровня вместо одного гейта — разбор, почему так:

   1. Базовая Метрика 109945462 грузится СРАЗУ, без баннера: визиты,
      источники, цели, показатель отказов, trackLinks. Это обезличенная
      статистика, которую /policy уже декларирует. Раньше счётчик стоял
      за жёстким гейтом согласия — до Метрики доезжала малая доля кликов
      из Вебмастера/GSC. Цели 578168283/578168629/578168992/578169121
      кормят автостратегии Яндекс.Директа.

   2. Вебвизор и карта кликов — ТОЛЬКО при сохранённом согласии.
      Метрика включает их в момент init и не умеет поднимать после,
      поэтому режим выбирается один раз при загрузке: нажавший
      "Разрешить" получает полный режим со следующей страницы.

   3. GA4 — только при согласии (данные уходят за границу).

   Фикс 17.09.2026:
   - убран ym init option defer:true (хит уходил только после onload —
     робот Метрики и часть визитов не засчитывались → CS_ERR_UNKNOWN);
   - tag.js?id=… как в официальном сниппете;
   - noscript-пиксель watch в HTML (см. build_static_site WOW_SNIPPET).

   Ключ согласия читаем из localStorage напрямую: foxi-consent.js
   подключён ПОСЛЕ этого файла. */
(function () {
  var YM_ID = 109945462;
  var GA_ID = "G-9XMYR6MJGL";
  var CONSENT_KEY = "fxb_cookie_consent_v1"; // см. foxi-consent.js
  var ymLoaded = false;
  var gaLoaded = false;

  function consentAccepted() {
    try {
      var raw = localStorage.getItem(CONSENT_KEY);
      return !!(raw && JSON.parse(raw).v === "accept");
    } catch (e) {
      return false;
    }
  }

  function loadMetrika(extended) {
    if (ymLoaded) { return; }
    ymLoaded = true;
    var tagSrc = "https://mc.yandex.ru/metrika/tag.js?id=" + YM_ID;
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) { return; }
      }
      k = e.createElement(t); a = e.getElementsByTagName(t)[0];
      k.async = 1; k.src = r; a.parentNode.insertBefore(k, a);
    })(window, document, "script", tagSrc, "ym");

    var opts = {
      ssr: true,
      trackLinks: true,
      accurateTrackBounce: true,
      clickmap: !!extended,
      webvisor: !!extended,
      ecommerce: "dataLayer",
      referrer: document.referrer,
      url: location.href
    };
    ym(YM_ID, "init", opts);
  }

  function loadGA4() {
    if (gaLoaded) { return; }
    gaLoaded = true;
    var s = document.createElement("script");
    s.async = 1;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", GA_ID);
  }

  var accepted = consentAccepted();
  try { loadMetrika(accepted); } catch (err) {}
  if (accepted) { try { loadGA4(); } catch (err) {} }

  document.addEventListener("fxb-consent", function (e) {
    if (!e || !e.detail || e.detail.v !== "accept") { return; }
    try { loadGA4(); } catch (err) {}
  });
})();
