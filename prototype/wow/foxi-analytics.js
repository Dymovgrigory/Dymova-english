/* Foxinburg analytics loader (сессия 59, пересмотрен 14.09.2026).

   Два уровня вместо одного гейта — разбор, почему так:

   1. Базовая Метрика 109945462 грузится СРАЗУ, без баннера: визиты,
      источники, цели, показатель отказов, trackLinks. Это обезличенная
      статистика, которую /policy уже декларирует ("Оператор обрабатывает
      обезличенные данные о Пользователе в случае, если это разрешено
      в настройках браузера"). Раньше счётчик стоял за жёстким гейтом,
      и это стоило дорого: сверка 14.09.2026 показала, что до Метрики
      доезжало ~35 визитов из поиска против ~502 кликов по данным самих
      Вебмастера и Search Console — около 7%. Цели 578168283/578168629/
      578168992/578169121 кормят автостратегии Яндекс.Директа, то есть
      стратегии обучались на шуме. Плюс Яндекс не видел счётчик вообще
      и держал замечание NO_METRIKA_COUNTER (робот баннер не нажимает).

   2. Вебвизор и карта кликов — ТОЛЬКО при сохранённом согласии: они
      пишут запись сессии и ввод в формы, и вот это уже разумно считать
      чувствительным. Метрика включает их в момент init и не умеет
      поднимать после, поэтому режим выбирается один раз при загрузке:
      нажавший "Разрешить" получает полный режим со следующей страницы.

   3. GA4 — только при согласии: данные уходят за границу, это отдельный
      разговор про 242-ФЗ, и с обезличенной статистикой он не смешивается.

   Ключ согласия читаем из localStorage напрямую: foxi-consent.js
   (где живёт window.FXBConsent) подключён ПОСЛЕ этого файла, потому что
   иначе он успевает разослать событие до того, как мы на него подпишемся.
   Ключ общий, при переименовании править оба файла. */
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
      // приватный режим или заблокированное хранилище — считаем, что
      // расширенной аналитики нет, базовая при этом работает
      return false;
    }
  }

  function loadMetrika(extended) {
    if (ymLoaded) { return; }
    ymLoaded = true;
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
      trackLinks: true,
      accurateTrackBounce: true,
      defer: true,
      clickmap: extended,
      webvisor: extended
    });
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

  // Согласие дали прямо сейчас: GA4 поднимаем сразу, вебвизор и карту
  // кликов — со следующей загрузки страницы (Метрика не переинициализируется).
  document.addEventListener("fxb-consent", function (e) {
    if (!e || !e.detail || e.detail.v !== "accept") { return; }
    try { loadGA4(); } catch (err) {}
  });
})();
