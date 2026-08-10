/* Telegram Mini App «Фоксинбург».
 *
 * Устройство:
 * - личность пользователя = подписанный initData, он уходит на бэкенд
 *   заголовком X-Miniapp-Init-Data; initDataUnsafe используется ТОЛЬКО для
 *   приветствия в интерфейсе и никогда — как основание для доступа;
 * - навигация — стек экранов, кнопка «назад» Telegram снимает верхний экран;
 * - у каждого экрана свой MainButton, он же — единственная главная кнопка;
 * - все сетевые вызовы имеют таймаут и понятное состояние ошибки.
 */
(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  var HOME = "home";
  var REQUEST_TIMEOUT_MS = 20000;

  var state = {
    stack: [HOME],
    info: null,
    access: null,
    profile: null,
    format: "",
    homeworkFile: null,
    chatBusy: false,
  };

  /* ---------------------------------------------------------------- утилиты */

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function screenEl(name) {
    return document.querySelector('[data-screen="' + name + '"]');
  }

  /** Экранирование: данные приходят из базы знаний и от LLM — в innerHTML их
   *  вставлять без экранирования нельзя. */
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function haptic(kind) {
    try {
      var hf = tg && tg.HapticFeedback;
      if (!hf) return;
      if (kind === "success" || kind === "error" || kind === "warning") {
        hf.notificationOccurred(kind);
      } else {
        hf.impactOccurred(kind || "light");
      }
    } catch (e) {
      /* тактильная отдача необязательна */
    }
  }

  function initData() {
    return (tg && tg.initData) || "";
  }

  function inTelegram() {
    return Boolean(initData());
  }

  /* ------------------------------------------------------------- сеть */

  function request(path, options) {
    options = options || {};
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, options.timeout || REQUEST_TIMEOUT_MS);

    var headers = options.headers || {};
    if (initData()) {
      headers["X-Miniapp-Init-Data"] = initData();
      headers["X-Miniapp-Platform"] = "telegram";
    }

    return fetch(path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body,
      signal: controller.signal,
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            data.__status = response.status;
            return data;
          });
      })
      .finally(function () {
        clearTimeout(timer);
      });
  }

  function postJSON(path, body) {
    return request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /* -------------------------------------------------------- навигация */

  function current() {
    return state.stack[state.stack.length - 1];
  }

  function render() {
    var name = current();
    document.querySelectorAll("[data-screen]").forEach(function (section) {
      section.hidden = section.dataset.screen !== name;
    });
    window.scrollTo(0, 0);
    syncChrome();
  }

  function go(name) {
    if (name === current()) return;
    haptic("light");
    state.stack.push(name);
    render();
    onEnter(name);
  }

  function back() {
    if (state.stack.length <= 1) {
      if (tg && tg.close) tg.close();
      return;
    }
    haptic("light");
    state.stack.pop();
    render();
  }

  /** Кнопки Telegram зависят от экрана — держим их в одном месте, иначе
   *  MainButton легко «залипает» с обработчиком чужого экрана. */
  var mainButtonHandler = null;

  /** Есть ли рабочая MainButton. В клиентах старше 6.1 её нет, и без
   *  запасной кнопки в разметке экран заявки становится тупиком. */
  function hasMainButton() {
    return Boolean(tg && tg.MainButton && typeof tg.MainButton.setText === "function" && tg.isVersionAtLeast && tg.isVersionAtLeast("6.1"));
  }

  function showFallbackButtons(screenName) {
    document.querySelectorAll("[data-fallback-action]").forEach(function (button) {
      button.hidden = hasMainButton() || button.dataset.fallbackAction !== screenName;
    });
  }

  function setMainButton(text, handler) {
    if (!hasMainButton()) return;
    if (mainButtonHandler) {
      tg.MainButton.offClick(mainButtonHandler);
      mainButtonHandler = null;
    }
    if (!text || !handler) {
      tg.MainButton.hide();
      return;
    }
    mainButtonHandler = handler;
    tg.MainButton.setText(text);
    tg.MainButton.onClick(mainButtonHandler);
    tg.MainButton.show();
    tg.MainButton.enable();
  }

  function mainButtonProgress(on) {
    if (!hasMainButton()) return;
    if (on) tg.MainButton.showProgress(true);
    else tg.MainButton.hideProgress();
  }

  function syncChrome() {
    if (!tg) return;
    if (tg.BackButton) {
      if (state.stack.length > 1) tg.BackButton.show();
      else tg.BackButton.hide();
    }
    var name = current();
    showFallbackButtons(name);
    if (name === "signup") {
      setMainButton("Отправить заявку", submitLead);
    } else if (name === "homework") {
      setMainButton("Разобрать задание", submitHomework);
    } else if (name === "picker") {
      setMainButton("Записаться на диагностику", function () {
        go("signup");
      });
    } else {
      setMainButton(null, null);
    }
  }

  /* --------------------------------------------------------- экраны */

  function onEnter(name) {
    if (name === "catalog") renderCatalog();
    if (name === "branches") renderBranches();
    if (name === "picker") runPicker();
    if (name === "profile") loadProfile();
    if (name === "chat") focusChat();
  }

  /* --- подбор курса ------------------------------------------------ */

  function ageLabel(value) {
    var n = Number(value);
    if (n >= 18) return "взрослым";
    var last = n % 10;
    var teen = n % 100 >= 11 && n % 100 <= 14;
    if (!teen && last === 1) return n + " год";
    if (!teen && last >= 2 && last <= 4) return n + " года";
    return n + " лет";
  }

  var pickerTimer = null;

  function runPicker() {
    var age = $("#age").value;
    $("#age-value").textContent = ageLabel(age);
    var box = $("#picker-results");
    box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';

    clearTimeout(pickerTimer);
    pickerTimer = setTimeout(function () {
      var url =
        "/api/miniapp/recommend?age=" +
        encodeURIComponent(age) +
        "&fmt=" +
        encodeURIComponent(state.format);
      request(url)
        .then(function (data) {
          var items = data.recommendations || [];
          if (!items.length) {
            box.innerHTML =
              '<p class="empty">Точного совпадения нет — оставьте заявку, ' +
              "подберём программу вручную.</p>";
            return;
          }
          box.innerHTML = items
            .map(function (item) {
              return (
                '<article class="card card--match">' +
                (item.age ? '<span class="pill">' + esc(item.age) + "</span>" : "") +
                '<h3 class="card__title">' + esc(item.name) + "</h3>" +
                '<p class="card__text">' + esc(item.text || "") + "</p>" +
                "</article>"
              );
            })
            .join("");
        })
        .catch(function () {
          box.innerHTML =
            '<p class="empty">Не удалось загрузить программы. Проверьте связь и попробуйте ещё раз.</p>';
        });
    }, 180);
  }

  /* --- каталог и филиалы ------------------------------------------- */

  function renderCatalog() {
    var box = $("#catalog");
    if (!state.info) {
      box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
      return;
    }
    var formats = state.info.formats || [];
    var courses = state.info.courses || [];
    box.innerHTML =
      formats
        .map(function (f) {
          return (
            '<article class="card">' +
            (f.price ? '<span class="pill">' + esc(f.price) + "</span>" : "") +
            '<h3 class="card__title">' + esc(f.name) + "</h3>" +
            (f.location ? '<p class="card__text">' + esc(f.location) + "</p>" : "") +
            "</article>"
          );
        })
        .join("") +
      courses
        .map(function (c) {
          return (
            '<article class="card">' +
            '<h3 class="card__title">' + esc(c.name) + "</h3>" +
            '<p class="card__text">' + esc(c.description || c.note || "") + "</p>" +
            (c.price ? '<p class="card__meta">' + esc(c.price) + "</p>" : "") +
            "</article>"
          );
        })
        .join("") ||
      '<p class="empty">Каталог пока не загрузился.</p>';
  }

  function renderBranches() {
    var box = $("#branches");
    if (!state.info) {
      box.innerHTML = '<div class="skeleton"></div>';
      return;
    }
    var branches = state.info.branches || [];
    box.innerHTML =
      branches
        .map(function (b) {
          return (
            '<article class="card">' +
            '<h3 class="card__title">' + esc(b.name) + "</h3>" +
            '<p class="card__meta">📍 ' +
            (b.maps
              ? '<a href="' + esc(b.maps) + '" target="_blank" rel="noopener">' + esc(b.address) + "</a>"
              : esc(b.address)) +
            "</p>" +
            (b.phone
              ? '<p class="card__meta">☎ <a href="tel:' + esc(b.phone_tel || b.phone) + '">' + esc(b.phone) + "</a></p>"
              : "") +
            (b.work_hours ? '<p class="card__text">🕘 ' + esc(b.work_hours) + "</p>" : "") +
            "</article>"
          );
        })
        .join("") || '<p class="empty">Список филиалов пока не загрузился.</p>';
  }

  /* --- профиль ------------------------------------------------------ */

  function loadProfile() {
    var box = $("#profile");
    box.innerHTML = '<div class="skeleton"></div>';
    if (!inTelegram()) {
      box.innerHTML =
        '<p class="empty">Профиль доступен только внутри Telegram — ' +
        "откройте приложение кнопкой в чате с ботом.</p>";
      return;
    }
    request("/api/miniapp/profile")
      .then(function (data) {
        if (data.__status === 401) {
          box.innerHTML =
            '<p class="empty">Сессия истекла. Закройте и откройте приложение заново.</p>';
          return;
        }
        state.profile = data;
        var p = data.profile || {};
        var rows = [
          ["Родитель", p.fio_parent],
          ["Ребёнок", p.fio_child],
          ["Возраст", p.age],
          ["Телефон", p.phone],
          ["Филиал", p.branch],
          ["Программа", p.course],
        ].filter(function (row) {
          return row[1];
        });

        box.innerHTML =
          '<article class="card">' +
          '<h3 class="card__title">' + esc(data.display_name || "Ваш профиль") + "</h3>" +
          '<p class="card__text">' +
          (data.registered ? "Регистрация подтверждена" : "Регистрация не завершена") +
          "</p>" +
          "</article>" +
          (rows.length
            ? '<article class="card">' +
              rows
                .map(function (row) {
                  return '<p class="card__meta">' + esc(row[0]) + ": " + esc(row[1]) + "</p>";
                })
                .join("") +
              "</article>"
            : '<p class="empty">Пока пусто. Оставьте заявку — данные появятся здесь.</p>');
      })
      .catch(function () {
        box.innerHTML = '<p class="empty">Не удалось загрузить профиль. Попробуйте позже.</p>';
      });
  }

  /* --- заявка ------------------------------------------------------- */

  function setStatus(el, message, kind) {
    el.textContent = message;
    el.className = "status" + (kind ? " status--" + kind : "");
    el.hidden = !message;
  }

  function submitLead() {
    var status = $("#lead-status");
    var parent = $("#lf-parent");
    var phone = $("#lf-phone");
    var body = {
      fio_parent: parent.value.trim(),
      fio_child: $("#lf-child").value.trim(),
      age: $("#lf-age").value.trim(),
      phone: phone.value.trim(),
      branch: $("#lf-branch").value,
      comment: $("#lf-comment").value.trim(),
    };

    parent.setAttribute("aria-invalid", body.fio_parent ? "false" : "true");
    phone.setAttribute("aria-invalid", body.phone ? "false" : "true");
    if (!body.fio_parent || !body.phone) {
      haptic("error");
      setStatus(status, "Заполните имя и телефон — по ним администратор свяжется с вами.", "error");
      (body.fio_parent ? phone : parent).focus();
      return;
    }

    mainButtonProgress(true);
    setStatus(status, "Отправляю заявку…");

    postJSON("/api/miniapp/lead", body)
      .then(function (data) {
        if (data.ok) {
          haptic("success");
          setStatus(status, "Готово. Администратор перезвонит в рабочее время.", "ok");
          setMainButton(null, null);
          showFallbackButtons(null);
        } else {
          haptic("error");
          setStatus(status, data.error || "Заявка не ушла. Попробуйте ещё раз или позвоните нам.", "error");
        }
      })
      .catch(function () {
        haptic("error");
        setStatus(status, "Нет связи с сервером. Проверьте интернет и повторите.", "error");
      })
      .finally(function () {
        mainButtonProgress(false);
      });
  }

  /* --- домашка ------------------------------------------------------ */

  function submitHomework() {
    var status = $("#hw-status");
    var answer = $("#hw-answer");
    answer.hidden = true;

    if (!state.homeworkFile) {
      haptic("error");
      setStatus(status, "Сначала прикрепите фото задания.", "error");
      return;
    }

    var form = new FormData();
    form.append("image", state.homeworkFile);
    form.append("note", $("#hw-note").value.trim());
    if (initData()) form.append("init_data", initData());

    mainButtonProgress(true);
    setStatus(status, "Фокси разбирает задание — обычно 10–20 секунд…");

    request("/api/miniapp/homework", { method: "POST", body: form, timeout: 90000 })
      .then(function (data) {
        if (data.ok && data.explanation) {
          haptic("success");
          setStatus(status, "Разбор готов:", "ok");
          answer.textContent = data.explanation;
          answer.hidden = false;
        } else {
          haptic("error");
          setStatus(
            status,
            data.error || data.detail || "Не получилось прочитать фото. Снимите задание крупнее и ровнее.",
            "error"
          );
        }
      })
      .catch(function () {
        haptic("error");
        setStatus(status, "Не дождался ответа. Попробуйте ещё раз через минуту.", "error");
      })
      .finally(function () {
        mainButtonProgress(false);
      });
  }

  /* --- чат ---------------------------------------------------------- */

  function addBubble(text, who, extraClass) {
    var log = $("#chat-log");
    var bubble = document.createElement("div");
    bubble.className = "bubble bubble--" + who + (extraClass ? " " + extraClass : "");
    bubble.textContent = text;
    log.appendChild(bubble);
    bubble.scrollIntoView({ block: "nearest" });
    return bubble;
  }

  function focusChat() {
    if (!$("#chat-log").children.length) {
      addBubble(
        inTelegram()
          ? "Привет! Спросите о курсах, ценах или записи — отвечу здесь же."
          : "Чат доступен внутри Telegram. Откройте приложение кнопкой в чате с ботом.",
        "bot"
      );
    }
  }

  function sendChat(event) {
    event.preventDefault();
    var input = $("#chat-input");
    var text = input.value.trim();
    if (!text || state.chatBusy) return;
    if (!inTelegram()) {
      addBubble("Здесь нужна авторизация Telegram — откройте приложение из чата с ботом.", "bot");
      return;
    }

    state.chatBusy = true;
    $(".composer__send").disabled = true;
    input.value = "";
    addBubble(text, "user");
    var pending = addBubble("Фокси печатает…", "bot", "bubble--typing");

    postJSON("/api/miniapp/chat", { text: text })
      .then(function (data) {
        pending.classList.remove("bubble--typing");
        pending.textContent =
          data.reply ||
          data.error ||
          "Не получилось ответить с первого раза. Напишите ещё раз, пожалуйста.";
        if (data.reply) haptic("light");
      })
      .catch(function () {
        pending.classList.remove("bubble--typing");
        pending.textContent = "Связь пропала. Попробуйте отправить сообщение ещё раз.";
      })
      .finally(function () {
        state.chatBusy = false;
        $(".composer__send").disabled = false;
      });
  }

  /* ------------------------------------------------------------ старт */

  function applyTheme() {
    if (!tg) return;
    document.documentElement.style.colorScheme = tg.colorScheme || "light";
  }

  function loadInfo() {
    return request("/api/miniapp/info")
      .then(function (data) {
        state.info = data;
        state.access = data.access || null;
        if (state.access && state.access.display_name) {
          $("#greeting-title").textContent = "Здравствуйте, " + state.access.display_name;
          $("#greeting-sub").textContent = "Чем помочь сегодня?";
        }
        $("#profile-teaser").textContent =
          state.access && state.access.registered ? "Открыт" : "Заполнить";
        if (current() === "catalog") renderCatalog();
        if (current() === "branches") renderBranches();
      })
      .catch(function () {
        $("#profile-teaser").textContent = "Нет связи";
      });
  }

  function bind() {
    document.querySelectorAll("[data-go]").forEach(function (el) {
      el.addEventListener("click", function () {
        go(el.dataset.go);
      });
    });

    $("#age").addEventListener("input", runPicker);

    document.querySelectorAll(".segmented__opt").forEach(function (opt) {
      opt.addEventListener("click", function () {
        document.querySelectorAll(".segmented__opt").forEach(function (other) {
          other.classList.toggle("is-active", other === opt);
        });
        state.format = opt.dataset.format;
        haptic("light");
        runPicker();
      });
    });

    $("#hw-file").addEventListener("change", function (event) {
      var file = event.target.files && event.target.files[0];
      state.homeworkFile = file || null;
      var preview = $("#hw-preview");
      if (file) {
        preview.src = URL.createObjectURL(file);
        preview.hidden = false;
        $("#hw-hint").textContent = "Заменить фото";
      } else {
        preview.hidden = true;
        $("#hw-hint").textContent = "Выбрать фото задания";
      }
    });

    document
      .querySelector('[data-fallback-action="homework"]')
      .addEventListener("click", submitHomework);

    $("#chat-form").addEventListener("submit", sendChat);
    $("#lead-form").addEventListener("submit", function (event) {
      event.preventDefault();
      submitLead();
    });

    window.addEventListener("online", function () {
      $("#offline").hidden = true;
      loadInfo();
    });
    window.addEventListener("offline", function () {
      $("#offline").hidden = false;
    });
  }

  function start() {
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
      applyTheme();
      tg.onEvent("themeChanged", applyTheme);
      if (tg.BackButton) tg.BackButton.onClick(back);
      // Приветствие по имени — из initDataUnsafe: это исключительно текст на
      // экране, никаких прав оно не даёт (права — только по подписи).
      var user = tg.initDataUnsafe && tg.initDataUnsafe.user;
      if (user && user.first_name) {
        $("#greeting-title").textContent = "Здравствуйте, " + user.first_name;
        $("#greeting-sub").textContent = "Чем помочь сегодня?";
      }
    }

    bind();
    if (!navigator.onLine) $("#offline").hidden = false;

    // Глубокие ссылки: t.me/bot/app?startapp=signup открывает нужный экран.
    var startParam =
      (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) ||
      (location.hash || "").replace("#", "");
    if (startParam && screenEl(startParam) && startParam !== HOME) {
      state.stack = [HOME, startParam];
    }

    render();
    onEnter(current());
    loadInfo();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
