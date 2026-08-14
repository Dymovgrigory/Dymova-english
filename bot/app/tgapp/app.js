/**
 * Мини-приложение Фоксинбурга.
 *
 * Механика отличается от прежней версии. Раньше это была стопка экранов с
 * кнопкой «назад»: любое действие уводило человека с главной и теряло
 * контекст. Теперь два независимых слоя:
 *
 *   1. Разделы — постоянный док внизу. Переключение мгновенное, положение
 *      прокрутки каждого раздела сохраняется, кнопка «назад» не нужна.
 *   2. Действия — лист снизу. Подбор, запись, домашка, тест уровня и видео
 *      педагога открываются поверх текущего раздела и закрываются свайпом,
 *      кнопкой или системной «назад».
 *
 * Личность пользователя — подписанный initData, он уходит на бэкенд
 * заголовком X-Miniapp-Init-Data; initDataUnsafe нигде не служит основанием
 * доступа. Всё, что показывает приложение, приходит с сервера: тексты о
 * школе, педагоги, шаги зачисления, вопросы теста. В вёрстке нет ни одного
 * факта — иначе он разойдётся с реальностью на первой правке прайса.
 *
 * Приложение обязано работать и без Telegram (обычный браузер), и без сети:
 * тогда закрыты личные разделы, а витрина показывает последнее загруженное.
 */
(function () {
  "use strict";

  /* Одно приложение на две площадки. Мост определяется по тому, кто из них
     создал свой объект: у Telegram это window.Telegram.WebApp, у MAX —
     window.WebApp. Всё остальное — общее, поэтому MAX больше не может
     отстать от Telegram на редизайн, как это уже случилось. */
  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  var max = !tg ? window.WebApp || (window.max && window.max.WebApp) || null : null;
  var bridge = tg || max;
  var PLATFORM = tg ? "telegram" : max ? "max" : "web";
  var REQUEST_TIMEOUT_MS = 15000;
  var TABS = ["home", "programs", "team", "chat", "profile"];

  var state = {
    tab: "home",
    sheet: null,
    info: null,
    access: null,
    profile: null,
    format: "",
    ageFilter: "",
    homeworkFile: null,
    chatBusy: false,
    quiz: { questions: [], index: 0, answers: {} },
    me: null, // что мы знаем о человеке после теста и подбора
    cabinet: null, // сводка кабинета с сервера
    activeChild: 0, // выбранный ребёнок в кабинете (индекс в cabinet.children)
    scroll: {},
  };

  /* ---------------------------------------------------------------- утилиты */

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function all(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  /** Подписка, которая переживает отсутствие элемента.
   *
   *  После обновления браузер может отдать закэшированную разметку вместе с
   *  новым скриптом. Одного null в bind() хватало, чтобы приложение не
   *  запустилось вообще: человек видел пустой экран вместо витрины. */
  function on(selector, event, handler, options) {
    var node = typeof selector === "string" ? $(selector) : selector;
    if (!node) return null;
    node.addEventListener(event, handler, options);
    return node;
  }

  /** Экранирование: данные приходят из базы знаний и от LLM — в innerHTML их
   *  вставлять без экранирования нельзя. */
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  /** Всплеск чернил в шапке как реакция на успех: жидкость вспыхивает
   *  цветом там, где раньше подпрыгивал маскот. */
  function mascot(event) {
    if (event !== "success") return;
    if (typeof window.foxiSplash === "function") window.foxiSplash();
  }

  function haptic(kind) {
    try {
      var hf = bridge && bridge.HapticFeedback;
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
    return (bridge && bridge.initData) || "";
  }

  /** Есть ли подписанная личность: только с ней открыт личный кабинет. */
  function signedIn() {
    return Boolean(initData());
  }

  function toast(text) {
    var box = $("#toast");
    box.textContent = text;
    box.hidden = false;
    clearTimeout(box._timer);
    box._timer = setTimeout(function () {
      box.hidden = true;
    }, 2600);
  }

  /** Память между запусками. В вебвью хранилище иногда запрещено — тогда
   *  приложение просто забывает человека, но не падает. */
  function remember(key, value) {
    try {
      window.localStorage.setItem("foxi:" + key, JSON.stringify(value));
    } catch (e) {
      /* приватный режим — переживём */
    }
  }

  function recall(key) {
    try {
      return JSON.parse(window.localStorage.getItem("foxi:" + key));
    } catch (e) {
      return null;
    }
  }

  /* ------------------------------------------------------------------- сеть */

  function request(path, options) {
    options = options || {};
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, options.timeout || REQUEST_TIMEOUT_MS);

    var headers = options.headers || {};
    if (initData()) {
      headers["X-Miniapp-Init-Data"] = initData();
      headers["X-Miniapp-Platform"] = PLATFORM;
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

  /* -------------------------------------------------------------- разделы */

  function goTab(name) {
    if (TABS.indexOf(name) < 0 || name === state.tab) return;
    // Положение прокрутки принадлежит разделу, а не странице: вернувшись,
    // человек должен оказаться там, где был.
    state.scroll[state.tab] = window.scrollY;
    state.tab = name;

    all("[data-tab]").forEach(function (section) {
      section.hidden = section.dataset.tab !== name;
    });
    all(".dock__btn").forEach(function (button) {
      button.classList.toggle("is-active", button.dataset.tabGo === name);
    });

    window.scrollTo(0, state.scroll[name] || 0);
    haptic("light");
    syncChrome();

    if (name === "programs") renderCatalog();
    if (name === "team") renderTeam();
    if (name === "profile") loadCabinet();
    if (name === "chat") greetInChat();
  }

  /* ---------------------------------------------------------------- листы */

  var SHEETS = {
    quiz: { title: "Тест уровня", build: buildQuiz },
    picker: { title: "Подбор курса", build: buildPicker },
    signup: { title: "Запись на занятие", build: buildSignup },
    homework: { title: "Помощь с домашкой", build: buildHomework },
    "child-edit": { title: "Карточка ребёнка", build: buildChildEdit },
  };

  function showSheet(title, html) {
    $("#sheet-title").textContent = title;
    $("#sheet-body").innerHTML = html;
    var sheet = $("#sheet");
    sheet.hidden = false;
    // Кадр между показом и классом нужен, чтобы браузер успел применить
    // начальное состояние и анимация действительно проигралась.
    requestAnimationFrame(function () {
      sheet.classList.add("is-open");
    });
    document.body.classList.add("is-locked");
    syncChrome();
  }

  function openSheet(name) {
    var config = SHEETS[name];
    if (!config) return;
    state.sheet = name;
    showSheet(config.title, "");
    config.build($("#sheet-body"));
    haptic("light");
  }

  function closeSheet() {
    var sheet = $("#sheet");
    if (sheet.hidden) return;
    sheet.classList.remove("is-open");
    document.body.classList.remove("is-locked");
    state.sheet = null;
    setTimeout(function () {
      sheet.hidden = true;
      $("#sheet-body").innerHTML = "";
    }, 220);
    syncChrome();
  }

  /** Системная кнопка «назад» закрывает лист, а не приложение. */
  function syncChrome() {
    if (!bridge || !bridge.BackButton) return;
    try {
      if (state.sheet || state.tab !== "home") bridge.BackButton.show();
      else bridge.BackButton.hide();
      if (bridge.MainButton) bridge.MainButton.hide();
    } catch (e) {
      /* старые версии клиента не знают этих кнопок */
    }
  }

  /* ----------------------------------------------------------- тест уровня */

  function buildQuiz(box) {
    if (!state.quiz.questions.length) {
      box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
      request("/api/miniapp/level-test")
        .then(function (data) {
          state.quiz.questions = data.questions || [];
          state.quiz.index = 0;
          state.quiz.answers = {};
          if (state.sheet === "quiz") renderQuizStep(box);
        })
        .catch(function () {
          box.innerHTML = '<p class="empty">Тест не загрузился. Попробуйте позже.</p>';
        });
      return;
    }
    state.quiz.index = 0;
    state.quiz.answers = {};
    renderQuizStep(box);
  }

  function renderQuizStep(box) {
    var quiz = state.quiz;
    var question = quiz.questions[quiz.index];
    if (!question) {
      finishQuiz(box);
      return;
    }

    // Точки вместо полосы: видно не только «сколько прошли», но и сколько
    // всего — пять коротких шагов не пугают, а полоса на 20% пугает.
    var dots = quiz.questions
      .map(function (_, i) {
        var state_ = i < quiz.index ? " is-done" : i === quiz.index ? " is-now" : "";
        return '<span class="quiz__dot' + state_ + '"></span>';
      })
      .join("");

    box.innerHTML =
      '<div class="quiz">' +
      '<div class="quiz__dots">' + dots + "</div>" +
      '<p class="quiz__step">Вопрос ' + (quiz.index + 1) + " из " + quiz.questions.length + "</p>" +
      '<p class="quiz__prompt">' + esc(question.prompt) + "</p>" +
      '<p class="quiz__hint">' + esc(question.hint) + "</p>" +
      '<div class="quiz__options">' +
      (question.options || [])
        .map(function (option, index) {
          return '<button class="quiz__opt" data-answer="' + index + '">' + esc(option) + "</button>";
        })
        .join("") +
      "</div></div>";

    all(".quiz__opt", box).forEach(function (button) {
      button.addEventListener("click", function () {
        if (box.dataset.locked) return;
        // Замок на время показа ответа: два быстрых нажатия иначе
        // проскакивают вопрос.
        box.dataset.locked = "1";
        quiz.answers[question.id] = Number(button.dataset.answer);
        button.classList.add("is-picked");
        haptic("light");
        setTimeout(function () {
          delete box.dataset.locked;
          quiz.index += 1;
          renderQuizStep(box);
        }, 260);
      });
    });
  }

  function finishQuiz(box) {
    box.innerHTML = '<div class="skeleton"></div>';
    postJSON("/api/miniapp/level-test", {
      answers: state.quiz.answers,
      // Попытка сохраняется на сервере за выбранным ребёнком — результат
      // больше не зависит от кэша браузера.
      child_id: currentChildId(),
    })
      .then(function (data) {
        var result = data.result;
        if (!result) throw new Error("нет результата");

        state.me = Object.assign({}, state.me, { level: result.level });
        remember("me", state.me);
        renderPulse();
        haptic("success");
        mascot("success");
        celebrate();

        // Кольцо результата: доля верных ответов видна одним взглядом.
        var ratio = result.total ? result.correct / result.total : 0;
        var marks = (result.details || [])
          .map(function (d, i) {
            return (
              '<span class="mark' + (d.correct ? " is-ok" : "") + '">' +
              (i + 1) + "</span>"
            );
          })
          .join("");

        box.innerHTML =
          '<div class="result">' +
          '<div class="result__ring" style="--ratio:' + ratio + '">' +
          '<span class="result__level">' + esc(result.level) + "</span>" +
          "</div>" +
          '<p class="result__title">' + esc(result.title) + "</p>" +
          '<p class="result__score">Верно ' + result.correct + " из " + result.total + "</p>" +
          '<div class="result__marks">' + marks + "</div>" +
          '<p class="result__text">' + esc(result.text) + "</p>" +
          '<p class="result__note">' + esc(result.disclaimer) + "</p>" +
          '<button class="primary primary--glow" data-sheet="signup">Записаться на диагностику</button>' +
          '<button class="ghost" data-sheet="picker">Подобрать программу под уровень</button>' +
          '<button class="ghost ghost--quiet" data-sheet="quiz">Пройти ещё раз</button>' +
          "</div>";
      })
      .catch(function () {
        box.innerHTML = '<p class="empty">Не удалось проверить ответы. Попробуйте ещё раз.</p>';
      });
  }

  /** Короткий залп конфетти. Рисуется на canvas и сам себя убирает: это
   *  награда за пройденный шаг, а не постоянный элемент интерфейса. */
  function celebrate() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var canvas = document.createElement("canvas");
    canvas.className = "confetti";
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.body.appendChild(canvas);

    var ctx = canvas.getContext("2d");
    var colors = ["#ffb703", "#6b4de6", "#24c6a0", "#ff6b8b"];
    var pieces = [];
    for (var i = 0; i < 70; i++) {
      pieces.push({
        x: canvas.width / 2 + (Math.random() - 0.5) * 120,
        y: canvas.height * 0.35,
        vx: (Math.random() - 0.5) * 9,
        vy: Math.random() * -11 - 3,
        size: 4 + Math.random() * 6,
        color: colors[i % colors.length],
        spin: (Math.random() - 0.5) * 0.3,
        angle: Math.random() * Math.PI,
      });
    }

    var started = performance.now();
    (function frame(now) {
      var elapsed = now - started;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach(function (p) {
        p.vy += 0.38;
        p.x += p.vx;
        p.y += p.vy;
        p.angle += p.spin;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.angle);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = Math.max(0, 1 - elapsed / 1800);
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        ctx.restore();
      });
      if (elapsed < 1800) requestAnimationFrame(frame);
      else canvas.remove();
    })(started);
  }

  /* --------------------------------------------------------- подбор курса */

  function buildPicker(box) {
    var me = state.me || {};
    box.innerHTML =
      '<div class="picker">' +
      '<p class="picker__q">Для кого подбираем?</p>' +
      '<div class="picker__row" data-group="who">' +
      ["Ребёнку", "Подростку", "Себе"]
        .map(function (label, index) {
          return (
            '<button class="pill' + (index === 0 ? " is-active" : "") + '" data-value="' +
            esc(label) + '">' + esc(label) + "</button>"
          );
        })
        .join("") +
      "</div>" +
      '<p class="picker__q">Возраст</p>' +
      '<div class="ruler">' +
      '<input id="age" class="ruler__input" type="range" min="3" max="20" step="1" value="' +
      (me.age || 9) + '" aria-label="Возраст ученика" />' +
      '<output class="ruler__value" id="age-value" for="age">' + (me.age || 9) + " лет</output>" +
      "</div>" +
      '<p class="picker__q">Формат</p>' +
      '<div class="picker__row" data-group="format">' +
      '<button class="pill is-active" data-value="">Любой</button>' +
      '<button class="pill" data-value="offline">Офлайн</button>' +
      '<button class="pill" data-value="online">Онлайн</button>' +
      "</div>" +
      '<div id="picker-results" class="results"></div>' +
      "</div>";

    all("[data-group] .pill", box).forEach(function (pill) {
      pill.addEventListener("click", function () {
        var group = pill.parentNode;
        all(".pill", group).forEach(function (other) {
          other.classList.toggle("is-active", other === pill);
        });
        if (group.dataset.group === "format") state.format = pill.dataset.value;
        haptic("light");
        runPicker();
      });
    });

    $("#age", box).addEventListener("input", function (event) {
      $("#age-value", box).textContent = event.target.value + " лет";
      state.me = Object.assign({}, state.me, { age: Number(event.target.value) });
      remember("me", state.me);
      renderPulse();
      runPicker();
    });

    runPicker();
  }

  function runPicker() {
    var box = $("#picker-results");
    if (!box) return;
    var ageInput = $("#age");
    var age = (ageInput && ageInput.value) || "9";
    box.innerHTML = '<div class="skeleton"></div>';
    request(
      "/api/miniapp/recommend?age=" + encodeURIComponent(age) +
        "&fmt=" + encodeURIComponent(state.format)
    )
      .then(function (data) {
        if (data.__status === 403) {
          box.innerHTML =
            '<p class="empty">' + esc(data.error || "Раздел откроется после регистрации") + "</p>";
          return;
        }
        var items = data.recommendations || [];
        box.innerHTML =
          items
            .map(function (item) {
              return (
                '<article class="result-card">' +
                (item.age ? '<span class="rail__age">' + esc(item.age) + "</span>" : "") +
                '<h3 class="rail__name">' + esc(item.name) + "</h3>" +
                '<p class="rail__text">' + esc(item.text || "") + "</p>" +
                '<button class="ghost" data-sheet="signup">Записаться на это</button>' +
                "</article>"
              );
            })
            .join("") || '<p class="empty">Для этого возраста подбор пока не готов.</p>';
      })
      .catch(function () {
        box.innerHTML = '<p class="empty">Не удалось загрузить подбор.</p>';
      });
  }

  /* ---------------------------------------------------------------- запись */

  function buildSignup(box) {
    var me = state.me || {};
    box.innerHTML =
      '<form id="lead-form" class="form" novalidate>' +
      '<label class="field"><span class="field__label">Ваше имя <em>обязательно</em></span>' +
      '<input id="lf-parent" name="fio_parent" type="text" autocomplete="name" placeholder="Иванова Анна" required /></label>' +
      '<label class="field"><span class="field__label">Имя ребёнка</span>' +
      '<input id="lf-child" name="fio_child" type="text" placeholder="Миша" /></label>' +
      '<label class="field"><span class="field__label">Возраст</span>' +
      '<input id="lf-age" name="age" type="number" min="2" max="99" value="' +
      esc(me.age || "") + '" placeholder="9" /></label>' +
      '<label class="field"><span class="field__label">Телефон <em>обязательно</em></span>' +
      '<input id="lf-phone" name="phone" type="tel" autocomplete="tel" placeholder="+7 999 000-00-00" required /></label>' +
      '<label class="field"><span class="field__label">Филиал или онлайн</span>' +
      '<select id="lf-branch" name="branch"><option value="">Выберите</option>' +
      "<option>Филиал на Лихачевском</option><option>Филиал на Ракетостроителей</option><option>Онлайн</option>" +
      "</select></label>" +
      '<label class="field"><span class="field__label">Комментарий</span>' +
      '<textarea id="lf-comment" name="comment" rows="2" placeholder="Удобное время, пожелания"></textarea></label>' +
      '<button type="submit" class="primary primary--glow">Отправить заявку</button>' +
      '<p id="lead-status" class="status" hidden></p>' +
      "</form>";

    $("#lead-form", box).addEventListener("submit", function (event) {
      event.preventDefault();
      submitLead();
    });
  }

  function submitLead() {
    var status = $("#lead-status");
    var body = {
      fio_parent: $("#lf-parent").value.trim(),
      fio_child: $("#lf-child").value.trim(),
      age: $("#lf-age").value.trim(),
      phone: $("#lf-phone").value.trim(),
      branch: $("#lf-branch").value,
      comment: $("#lf-comment").value.trim(),
    };
    if (!body.fio_parent || !body.phone) {
      var form = $("#lead-form");
      if (form) form.classList.add("is-tried");
      status.hidden = false;
      status.textContent = "Заполните имя и телефон — без них не сможем перезвонить.";
      haptic("error");
      return;
    }
    status.hidden = false;
    status.textContent = "Отправляю…";

    postJSON("/api/miniapp/lead", body)
      .then(function (data) {
        if (data.ok) {
          status.textContent = "Готово. Администратор свяжется с вами.";
          haptic("success");
          mascot("success");
          celebrate();
          setTimeout(closeSheet, 1400);
        } else {
          status.textContent = data.error || "Не получилось отправить. Попробуйте ещё раз.";
          haptic("error");
        }
      })
      .catch(function () {
        status.textContent = "Нет связи. Заявка не ушла.";
        haptic("error");
      });
  }

  /* -------------------------------------------------------------- домашка */

  function buildHomework(box) {
    box.innerHTML =
      '<div class="hw">' +
      '<p class="lede">Сфотографируйте задание — Фокси объяснит, как его решать. Бесплатно.</p>' +
      '<label class="drop"><input id="hw-file" type="file" accept="image/*" hidden />' +
      '<span id="hw-hint">Выбрать фото задания</span>' +
      '<img id="hw-preview" class="drop__preview" alt="" hidden /></label>' +
      '<input id="hw-note" type="text" placeholder="Например: задание 3, перевести предложения" />' +
      '<button type="button" class="primary" data-fallback-action="homework">Разобрать задание</button>' +
      '<p id="hw-status" class="status" hidden></p>' +
      '<div id="hw-answer" class="answer" hidden></div>' +
      "</div>";

    $("#hw-file", box).addEventListener("change", function (event) {
      var file = event.target.files && event.target.files[0];
      state.homeworkFile = file || null;
      var preview = $("#hw-preview", box);
      if (file) {
        preview.src = URL.createObjectURL(file);
        preview.hidden = false;
        $("#hw-hint", box).textContent = "Заменить фото";
      } else {
        preview.hidden = true;
        $("#hw-hint", box).textContent = "Выбрать фото задания";
      }
    });

    $('[data-fallback-action="homework"]', box).addEventListener("click", submitHomework);
  }

  function submitHomework() {
    var status = $("#hw-status");
    var answer = $("#hw-answer");
    if (!state.homeworkFile) {
      status.hidden = false;
      status.textContent = "Сначала выберите фото задания.";
      return;
    }
    status.hidden = false;
    status.textContent = "Смотрю задание…";
    answer.hidden = true;

    var form = new FormData();
    // Поле и ответ — по серверному контракту (его же использует legacy /app).
    form.append("image", state.homeworkFile);
    form.append("note", $("#hw-note").value.trim());

    request("/api/miniapp/homework", { method: "POST", body: form, timeout: 90000 })
      .then(function (data) {
        if (data.__status === 403) {
          status.textContent = data.error || "Раздел откроется после регистрации.";
          return;
        }
        if (data.explanation) {
          status.hidden = true;
          answer.hidden = false;
          answer.textContent = data.explanation;
          haptic("success");
        } else {
          status.textContent = data.error || data.detail || "Не получилось разобрать задание.";
        }
      })
      .catch(function () {
        status.textContent = "Нет связи. Попробуйте позже.";
      });
  }

  /* ------------------------------------------------------------------ чат */

  function greetInChat() {
    var log = $("#chat-log");
    if (log.dataset.greeted) return;
    log.dataset.greeted = "1";
    addMessage("bot", "Спросите что угодно: программы, цены, расписание, как проходят занятия.");
  }

  function addMessage(role, text) {
    var log = $("#chat-log");
    var bubble = document.createElement("div");
    bubble.className = "bubble bubble--" + role;
    bubble.textContent = text;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  function sendChat(event) {
    event.preventDefault();
    var input = $("#chat-input");
    var text = input.value.trim();
    if (!text || state.chatBusy) return;
    input.value = "";
    addMessage("me", text);
    state.chatBusy = true;

    var typing = addMessage("bot", "…");
    typing.classList.add("bubble--typing");

    postJSON("/api/miniapp/chat", { text: text })
      .then(function (data) {
        typing.remove();
        if (data.__status === 403) {
          addMessage("bot", data.error || "Чат откроется после регистрации.");
          return;
        }
        addMessage("bot", data.reply || "Не удалось получить ответ.");
      })
      .catch(function () {
        typing.remove();
        addMessage("bot", "Нет связи. Попробуйте ещё раз.");
      })
      .finally(function () {
        state.chatBusy = false;
      });
  }

  /* ------------------------------------------------------- фразы в шапке */

  /** Фразы школы, которые сменяют друг друга под заголовком.
   *
   *  Это позиционирование, а не факты: ни цен, ни расписания, ни цифр,
   *  которые способны разойтись с базой знаний. Слоган школы стоит первым и
   *  остаётся в разметке — он виден и без скрипта.
   */
  var PHRASES = [
    "Английский не для школы, а для жизни",
    "Говорить — с первого занятия",
    "Мини-группы, а не поток",
    "Среда, в которой не переходят на русский",
    "Учим не для оценки, а для уверенности",
    "Тот случай, когда на занятия просятся сами",
  ];

  var PHRASE_HOLD_MS = 3200;   // сколько фраза стоит собранной
  var WORD_STAGGER_MS = 90;    // задержка между словами
  var phraseTimer = null;

  function startPhrases() {
    var box = $("#greeting-sub");
    if (!box) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var index = 0;
    showPhrase(box, PHRASES[0]);

    function next() {
      box.classList.add("is-out");
      phraseTimer = setTimeout(function () {
        index = (index + 1) % PHRASES.length;
        box.classList.remove("is-out");
        showPhrase(box, PHRASES[index]);
        phraseTimer = setTimeout(next, PHRASE_HOLD_MS + PHRASES[index].split(" ").length * WORD_STAGGER_MS);
      }, 340);
    }

    phraseTimer = setTimeout(next, PHRASE_HOLD_MS + PHRASES[0].split(" ").length * WORD_STAGGER_MS);
  }

  /** Фраза собирается по слову: каждое слово — свой элемент со своей
   *  задержкой. Пробел ставим отдельно, иначе строка не переносится. */
  function showPhrase(box, text) {
    box.textContent = "";
    text.split(" ").forEach(function (word, i) {
      var span = document.createElement("span");
      span.className = "word";
      span.textContent = word;
      span.style.transitionDelay = i * WORD_STAGGER_MS + "ms";
      box.appendChild(span);
      box.appendChild(document.createTextNode(" "));
      // Кадр без класса нужен, чтобы переход действительно проигрался.
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          span.classList.add("is-in");
        });
      });
    });
  }

  /* -------------------------------------------------------------- витрина */

  function renderHome() {
    if (!state.info) return;
    renderPromo();
    renderAdvantages();
    renderPath();
    renderFaq();
    renderHomeBranches();
    renderPulse();
    armReveals();
  }

  /** Персональная полоса: что мы уже знаем о человеке и что логично дальше. */
  function renderPulse() {
    var me = state.me || {};
    var pulse = $("#pulse");
    if (!pulse) return;
    if (me.level && me.age) {
      $("#pulse-title").textContent = "Уровень " + me.level + ", возраст " + me.age;
      $("#pulse-text").textContent = "Показать подходящие программы";
      pulse.dataset.sheet = "picker";
    } else if (me.level) {
      $("#pulse-title").textContent = "Ваш уровень: " + me.level;
      $("#pulse-text").textContent = "Подобрать программу под него";
      pulse.dataset.sheet = "picker";
    } else {
      $("#pulse-title").textContent = "Узнать уровень за минуту";
      $("#pulse-text").textContent = "Пять заданий — и сразу видно, с чего начинать";
      pulse.dataset.sheet = "quiz";
    }
  }

  function renderPromo() {
    var box = $("#promo-slot");
    var promos = (state.info.promos || []).filter(Boolean);
    var academy = state.info.summer_academy || null;
    var text = promos[0] || (academy && academy.note) || "";
    if (!text) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML =
      '<div class="promo reveal">' +
      '<span class="promo__badge">Сейчас в школе</span>' +
      '<p class="promo__text">' + esc(text) + "</p>" +
      "</div>";
  }

  function renderAdvantages() {
    var box = $("#home-advantages");
    box.innerHTML = (state.info.advantages || [])
      .slice(0, 4)
      .map(function (item) {
        return (
          '<article class="card">' +
          '<h3 class="card__title">' + esc(item.title) + "</h3>" +
          '<p class="card__text">' + esc(item.text) + "</p>" +
          "</article>"
        );
      })
      .join("");
  }

  function renderPath() {
    var box = $("#home-path");
    box.innerHTML = (state.info.enrollment_steps || [])
      .map(function (step) {
        return (
          '<li class="path__item">' +
          '<span class="path__num">' + esc(step.step) + "</span>" +
          '<div><h3 class="path__title">' + esc(step.title) + "</h3>" +
          '<p class="path__text">' + esc(step.text) + "</p></div>" +
          "</li>"
        );
      })
      .join("");
  }

  function renderFaq() {
    var box = $("#home-faq");
    box.innerHTML = (state.info.faq || [])
      .slice(0, 5)
      .map(function (item) {
        return (
          '<div class="faq__item">' +
          '<button type="button" class="faq__q">' + esc(item.q) +
          '<span class="faq__sign" aria-hidden="true">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>' +
          "</span></button>" +
          '<p class="faq__a">' + esc(item.a) + "</p>" +
          "</div>"
        );
      })
      .join("");

    all(".faq__q", box).forEach(function (button) {
      button.addEventListener("click", function () {
        var item = button.parentNode;
        var open = item.classList.contains("is-open");
        // Раскрыт всегда один вопрос: пять развёрнутых ответов не читаются.
        all(".faq__item", box).forEach(function (other) {
          other.classList.remove("is-open");
        });
        if (!open) item.classList.add("is-open");
        haptic("light");
      });
    });
  }

  function renderHomeBranches() {
    var box = $("#home-branches");
    box.innerHTML = (state.info.branches || []).slice(0, 2).map(branchCard).join("");
  }

  /** Карточка филиала: адрес ведёт в маршрут, телефон — в звонок.
   *
   *  Человеку с телефона нужно ровно два действия — доехать и позвонить.
   *  Раньше и то и другое было простым текстом, который приходилось
   *  выделять и копировать. */
  function branchCard(b) {
    var route = b.maps || ("https://yandex.ru/maps/?rtext=~" + encodeURIComponent(b.address || b.name));
    var phone = b.phone_tel || b.phone;
    return (
      '<article class="card branch">' +
      '<h3 class="card__title">' + esc(b.name) + "</h3>" +
      (b.address
        ? '<a class="branch__row" href="' + esc(route) + '" target="_blank" rel="noopener">' +
          '<span class="branch__ic" aria-hidden="true">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-5.3 7-11a7 7 0 1 0-14 0c0 5.7 7 11 7 11Z"/><circle cx="12" cy="10" r="2.6"/></svg>' +
          "</span>" +
          '<span class="branch__text">' + esc(b.address) + '<span class="branch__hint">Построить маршрут</span></span>' +
          "</a>"
        : "") +
      (phone
        ? '<a class="branch__row" href="tel:' + esc(phone) + '">' +
          '<span class="branch__ic" aria-hidden="true">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3h3l1.5 4-2 1.4a12 12 0 0 0 5.6 5.6L16 12l4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 3 6.2 2 2 0 0 1 5 4h1.5Z"/></svg>' +
          "</span>" +
          '<span class="branch__text">' + esc(b.phone) + '<span class="branch__hint">Позвонить</span></span>' +
          "</a>"
        : "") +
      (b.work_hours ? '<p class="branch__hours">' + esc(b.work_hours) + "</p>" : "") +
      "</article>"
    );
  }

  /* ------------------------------------------------------------- программы */

  function inAgeFilter(item) {
    if (!state.ageFilter) return true;
    var text = String(item.age || item.ages || "");
    var numbers = (text.match(/\d+/g) || []).map(Number);
    // «2-3 класс» — это классы, а не возраст: в первый класс идут в семь лет.
    // Без пересчёта курс для второклассников попадал в фильтр «3–6 лет».
    if (/класс/i.test(text)) {
      numbers = numbers.map(function (n) {
        return n + 6;
      });
    }
    if (state.ageFilter === "adult") {
      return /взросл/i.test(text) || numbers.some(function (n) {
        return n >= 18;
      });
    }
    if (!numbers.length) return false;
    var bounds = state.ageFilter.split("-").map(Number);
    var low = Math.min.apply(null, numbers);
    var high = Math.max.apply(null, numbers);
    return high >= bounds[0] && low <= bounds[1];
  }

  function renderCatalog() {
    var box = $("#catalog");
    if (!state.info) {
      box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
      return;
    }
    var items = (state.info.age_programs || [])
      .concat(state.info.courses || [])
      .filter(inAgeFilter);
    box.innerHTML =
      items
        .map(function (item) {
          var age = item.age || item.ages || "";
          var price = item.price || "";
          return (
            '<article class="result-card">' +
            (age ? '<span class="rail__age">' + esc(age) + "</span>" : "") +
            '<h3 class="rail__name">' + esc(item.name) + "</h3>" +
            '<p class="rail__text">' + esc(item.text || item.description || "") + "</p>" +
            (price ? '<p class="price">' + esc(price) + "</p>" : "") +
            '<button class="ghost" data-sheet="signup">Записаться</button>' +
            "</article>"
          );
        })
        .join("") || '<p class="empty">Под этот возраст программ не нашлось.</p>';
  }

  /* -------------------------------------------------------------- педагоги */

  function renderTeam() {
    var box = $("#team-list");
    if (!state.info) {
      box.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
      return;
    }
    var people = (state.info.team || []).filter(function (person) {
      return person.name;
    });
    box.innerHTML =
      people
        .map(function (person, index) {
          var video = person.video_intro || person.video_lesson || "";
          return (
            '<article class="person">' +
            '<div class="person__top">' +
            (person.photo
              ? '<img class="person__photo" src="' + esc(person.photo) + '" alt="" ' +
                'width="56" height="56" loading="lazy" decoding="async" />'
              : '<span class="person__avatar" aria-hidden="true">' +
                esc(String(person.name).slice(0, 1)) + "</span>") +
            '<div><h3 class="person__name">' + esc(person.name) + "</h3>" +
            '<p class="person__role">' + esc(person.role || "") + "</p></div>" +
            "</div>" +
            (person.about ? '<p class="person__about">' + esc(person.about) + "</p>" : "") +
            (video ? '<button class="ghost" data-video="' + index + '">Смотреть видео</button>' : "") +
            "</article>"
          );
        })
        .join("") || '<p class="empty">Список педагогов пока не загрузился.</p>';

    all("[data-video]", box).forEach(function (button) {
      button.addEventListener("click", function () {
        openVideo(people[Number(button.dataset.video)]);
      });
    });
  }

  /** Видео педагога в листе. Без автозапуска: тяжёлое видео в вебвью
   *  съедает трафик человека без спроса. */
  function openVideo(person) {
    if (!person) return;
    var sources = [
      { url: person.video_intro, label: "Видеовизитка" },
      { url: person.video_lesson, label: "Фрагмент урока" },
    ].filter(function (item) {
      return item.url;
    });
    if (!sources.length) return;

    state.sheet = "video";
    showSheet(
      person.name,
      '<div class="video">' +
        sources
          .map(function (item) {
            return (
              '<p class="video__label">' + esc(item.label) + "</p>" +
              '<video controls preload="none" playsinline src="' + esc(item.url) + '"></video>'
            );
          })
          .join("") +
        "</div>"
    );
    haptic("light");
  }

  /* -------------------------------------------------------------- кабинет */

  /* Кабинет — это раздел дока, а не лист. Лента блоков: кто я, ближайшее
     занятие, прогресс, заявки, что дальше. Каждое пустое состояние —
     предложение действия, а не сообщение об ошибке. */

  var LEVEL_ORDER = ["A0–A1", "A1–A2", "A2–B1", "B1+"];

  function kvRow(key, value) {
    return (
      '<div class="kv"><span class="kv__k">' + esc(key) + "</span>" +
      '<span class="kv__v">' + esc(value) + "</span></div>"
    );
  }

  function loadCabinet() {
    if (!signedIn()) {
      renderCabinetGuest();
      return;
    }
    markCabinetLoading();
    request("/api/miniapp/cabinet")
      .then(function (data) {
        if (data.__status === 401) {
          renderCabinetGuest();
          return;
        }
        state.cabinet = data;
        remember("cabinet", data);
        $("#offline").hidden = true;
        renderCabinet(data);
      })
      .catch(function () {
        // Нет связи: показываем последнее загруженное с честной пометкой,
        // а не пустой экран.
        var cached = recall("cabinet");
        $("#offline").hidden = false;
        if (cached) {
          state.cabinet = cached;
          renderCabinet(cached, true);
        } else {
          renderCabinetMessage(
            "Нет связи",
            "Как только сеть появится, кабинет загрузится сам. Пока можно посмотреть программы и педагогов — они на месте."
          );
        }
      });
  }

  function markCabinetLoading() {
    all(".cab__block").forEach(function (block) {
      block.innerHTML = '<div class="skeleton"></div>';
    });
  }

  function renderCabinetMessage(title, text, actionsHtml) {
    all(".cab__block").forEach(function (block) {
      block.innerHTML = "";
    });
    $("#cab-kids").innerHTML = "";
    $("#cab-greeting").textContent = title;
    $("#cab-sub").textContent = text;
    $("#cab-next").innerHTML = actionsHtml || "";
  }

  /** Не в мессенджере: объясняем, откуда открывается кабинет, и даём
   *  кнопку в бота. Никаких фальшивых данных. */
  function renderCabinetGuest() {
    var botUrl = botLink();
    renderCabinetMessage(
      "Кабинет открывается из чата",
      "Здесь будут ваши дети, их прогресс и расписание. Откройте приложение из чата с ботом — там оно знает, кто вы.",
      botUrl
        ? '<a class="primary primary--glow cab__cta" href="' + esc(botUrl) + '" target="_blank" rel="noopener">Перейти в бота</a>'
        : ""
    );
  }

  function botLink() {
    var social = (state.info && state.info.social) || {};
    return PLATFORM === "telegram"
      ? social.telegram || social.max_bot || ""
      : social.max_bot || social.telegram || "";
  }

  /** Есть личность, но регистрации нет: что даст регистрация и кнопка
   *  в чат с ботом, где она проходит. */
  function renderCabinetUnregistered() {
    renderCabinetMessage(
      "Осталось познакомиться",
      "",
      '<ul class="cab__perks">' +
        "<li>Карточка ребёнка: уровень, программа, расписание</li>" +
        "<li>История тестов уровня — видно динамику</li>" +
        "<li>Заявки и ближайшее занятие в одном месте</li>" +
        "</ul>" +
        '<button class="primary primary--glow cab__cta" data-cab-register>Пройти регистрацию</button>'
    );
    var btn = $("[data-cab-register]");
    if (btn) {
      btn.addEventListener("click", function () {
        askInChat("Хочу зарегистрироваться");
      });
    }
  }

  function renderCabinet(data, stale) {
    var kids = data.children || [];
    if (state.activeChild >= kids.length) state.activeChild = 0;
    var child = kids[state.activeChild] || null;

    $("#cab-greeting").textContent = data.greeting_name
      ? "Здравствуйте, " + data.greeting_name
      : "Кабинет";
    $("#cab-sub").textContent = stale
      ? "Нет связи — показаны данные последней загрузки, они могли устареть."
      : "Ваши дети, прогресс и занятия — всё своё в одном месте.";

    if (!data.registered) {
      renderCabinetUnregistered();
      return;
    }

    renderKids(kids);
    renderChildCard(child);
    renderLesson(data.schedule || {}, child);
    renderProgress(data.attempts || {}, child);
    renderLead(data.lead);
    renderNext(data.next_action, data.schedule);
  }

  function renderKids(kids) {
    var box = $("#cab-kids");
    if (!kids.length) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML =
      kids
        .map(function (kid, index) {
          return (
            '<button class="cab__kid' + (index === state.activeChild ? " is-active" : "") +
            '" data-kid="' + index + '" role="tab" aria-selected="' +
            (index === state.activeChild) + '">' +
            '<span class="cab__kid-name">' + esc(kid.name) + "</span>" +
            (kid.age ? '<span class="cab__kid-age">' + esc(kid.age) + "</span>" : "") +
            "</button>"
          );
        })
        .join("") +
      '<button class="cab__kid cab__kid--add" data-cab-add-child aria-label="Добавить ребёнка">+</button>';

    all("[data-kid]", box).forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.activeChild = Number(btn.dataset.kid);
        haptic("light");
        renderCabinet(state.cabinet);
      });
    });
    var add = $("[data-cab-add-child]", box);
    if (add) {
      add.addEventListener("click", function () {
        openSheet("child-edit");
      });
    }
  }

  function currentChild() {
    var kids = (state.cabinet && state.cabinet.children) || [];
    return kids[state.activeChild] || null;
  }

  function currentChildId() {
    var child = currentChild();
    return child ? child.id : null;
  }

  function renderChildCard(child) {
    var box = $("#cab-child");
    if (!child) {
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Карточка ребёнка</h3>' +
        '<p class="cab__text">Расскажите, кто будет заниматься: имя, возраст и уровень подтянутся в подбор программы и в чат с ботом.</p>' +
        '<button class="primary" data-cab-add-child>Добавить ребёнка</button>' +
        "</div>";
      var btn = $("[data-cab-add-child]", box);
      if (btn) btn.addEventListener("click", function () { openSheet("child-edit"); });
      return;
    }
    box.innerHTML =
      '<div class="cab__card">' +
      '<h3 class="cab__title">' + esc(child.name) + "</h3>" +
      '<div class="kv-list">' +
      (child.age ? kvRow("Возраст", child.age) : "") +
      (child.grade ? kvRow("Класс", child.grade) : "") +
      kvRow("Уровень", child.level || "пока не определён") +
      (child.program ? kvRow("Программа", child.program) : "") +
      "</div>" +
      '<button class="ghost" data-cab-edit-child>Изменить</button>' +
      "</div>";
    $("[data-cab-edit-child]", box).addEventListener("click", function () {
      openSheet("child-edit");
    });
  }

  function branchInfo(name) {
    var branches = (state.info && state.info.branches) || [];
    if (!name) return null;
    var clean = function (s) {
      return String(s || "").toLowerCase().replace(/ё/g, "е").replace(/[^а-яa-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
    };
    var hay = function (b) { return clean(b.name) + " " + clean(b.address); };
    var needle = clean(name);
    // Склонения ломают точное сравнение («Лихачёвский» vs «на Лихачевском»),
    // поэтому сравниваем по основам слов: хвост из 2–3 букв отбрасываем.
    var stems = needle.split(" ").filter(function (w) { return w.length >= 6; })
      .map(function (w) { return w.slice(0, -3); });
    for (var i = 0; i < branches.length; i++) {
      var text = hay(branches[i]);
      if (needle && text.indexOf(needle) >= 0) return branches[i];
      for (var j = 0; j < stems.length; j++) {
        if (stems[j].length >= 5 && text.indexOf(stems[j]) >= 0) return branches[i];
      }
    }
    return null;
  }

  function lessonActions(filial) {
    var branch = branchInfo(filial);
    var html = "";
    if (branch && (branch.maps || branch.address)) {
      var url = branch.maps ||
        "https://yandex.ru/maps/?text=" + encodeURIComponent(branch.address);
      html += '<a class="ghost" target="_blank" rel="noopener" href="' + esc(url) + '">Построить маршрут</a>';
    }
    if (branch && (branch.phone_tel || branch.phone)) {
      html += '<a class="ghost" href="tel:' + esc(branch.phone_tel || String(branch.phone).replace(/[^+\d]/g, "")) + '">Позвонить в филиал</a>';
    }
    return html;
  }

  function renderLesson(schedule, child) {
    var box = $("#cab-lesson");
    if (!schedule.has_import) {
      // Честный блок вместо пустой сетки недели: расписания нет, потому что
      // выгрузки ещё не было, — и вот что с этим сделать.
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Расписание</h3>' +
        '<p class="cab__text">Расписание появится, когда администратор загрузит его в бота. Обычно это раз в неделю.</p>' +
        '<button class="primary" data-cab-ask-schedule>Спросить расписание</button>' +
        "</div>";
      $("[data-cab-ask-schedule]", box).addEventListener("click", function () {
        askInChat("Подскажите, пожалуйста, расписание занятий");
      });
      return;
    }
    var lessons = schedule.lessons || [];
    var note = '<p class="cab__note">Данные на ' + esc(schedule.imported_label || "—") +
      (schedule.stale ? " · расписание могло измениться" : "") + "</p>";
    if (!lessons.length) {
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Расписание</h3>' +
        '<p class="cab__text">Выгрузка есть, но вашего расписания в ней пока нет. Уточните у администратора — возможно, строку не сопоставили.</p>' +
        '<button class="primary" data-cab-ask-schedule>Спросить расписание</button>' +
        note +
        "</div>";
      $("[data-cab-ask-schedule]", box).addEventListener("click", function () {
        askInChat("Подскажите, пожалуйста, расписание занятий");
      });
      return;
    }
    var next = schedule.next;
    var nextHtml = "";
    if (next) {
      nextHtml =
        '<div class="cab__next-lesson">' +
        '<p class="cab__next-when">' + esc(next.day_hint || next.weekday_label) +
        (next.time ? ", " + esc(next.time) : "") + "</p>" +
        (next.program ? '<p class="cab__next-what">' + esc(next.program) + "</p>" : "") +
        '<p class="cab__next-meta">' +
        [next.teacher, next.filial].filter(Boolean).map(esc).join(" · ") +
        "</p>" +
        '<div class="cab__actions">' + lessonActions(next.filial) + "</div>" +
        "</div>";
    }
    var weekHtml =
      lessons.length > 1
        ? '<ul class="cab__week">' +
          lessons
            .map(function (lesson) {
              return (
                "<li><b>" + esc(lesson.weekday_label || lesson.weekday) + "</b> " +
                esc(lesson.time || "") +
                (lesson.program ? " · " + esc(lesson.program) : "") +
                (lesson.student_name && (!child || lesson.student_name !== child.name)
                  ? " · " + esc(lesson.student_name)
                  : "") +
                "</li>"
              );
            })
            .join("") +
          "</ul>"
        : "";
    box.innerHTML =
      '<div class="cab__card">' +
      '<h3 class="cab__title">Ближайшее занятие</h3>' +
      nextHtml + weekHtml + note +
      "</div>";
  }

  function renderProgress(attempts, child) {
    var box = $("#cab-progress");
    if (!attempts.kind || attempts.kind === "none") {
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Прогресс</h3>' +
        '<p class="cab__text">Здесь будет динамика теста уровня' +
        (child ? " — " + esc(child.name) : "") +
        ". Первый результат появится сразу после прохождения.</p>" +
        '<button class="primary" data-sheet="quiz">Пройти тест уровня</button>' +
        "</div>";
      return;
    }
    if (attempts.kind === "single") {
      var point = attempts.points[0];
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Прогресс</h3>' +
        '<p class="cab__text">' + esc(attempts.phrase) + "</p>" +
        '<p class="cab__note">' + esc(point.level) + " · верно " + point.correct + " из " + point.total + "</p>" +
        "</div>";
      return;
    }
    box.innerHTML =
      '<div class="cab__card">' +
      '<h3 class="cab__title">Прогресс</h3>' +
      progressChart(attempts.points) +
      '<p class="cab__text">' + esc(attempts.phrase) + "</p>" +
      "</div>";
  }

  /** Линия уровня по попыткам. Шкала — коды уровней, а не проценты:
   *  процентов мы не измеряли. */
  function progressChart(points) {
    var W = 300, H = 120, PAD = 26;
    var ranks = points.map(function (p) {
      var rank = LEVEL_ORDER.indexOf(p.level);
      return rank < 0 ? 0 : rank;
    });
    var stepX = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
    var stepY = (H - PAD * 2) / (LEVEL_ORDER.length - 1);
    var coords = points.map(function (p, i) {
      return [PAD + i * stepX, H - PAD - ranks[i] * stepY];
    });
    var path = coords
      .map(function (c, i) {
        return (i ? "L" : "M") + c[0].toFixed(1) + " " + c[1].toFixed(1);
      })
      .join(" ");
    var dots = coords
      .map(function (c, i) {
        return (
          '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="5" class="cab__dot' +
          (i === coords.length - 1 ? " is-last" : "") + '">' +
          "<title>" + esc(points[i].date + " — " + points[i].level) + "</title></circle>"
        );
      })
      .join("");
    var labels = LEVEL_ORDER.map(function (level, i) {
      var y = H - PAD - i * stepY;
      return '<text x="2" y="' + (y + 3).toFixed(1) + '" class="cab__axis">' + esc(level) + "</text>";
    }).join("");
    return (
      '<svg class="cab__chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Динамика уровня">' +
      labels +
      '<path d="' + path + '" class="cab__line"/>' +
      dots +
      "</svg>"
    );
  }

  function renderLead(lead) {
    var box = $("#cab-lead");
    if (!lead) {
      box.innerHTML =
        '<div class="cab__card">' +
        '<h3 class="cab__title">Мои заявки</h3>' +
        '<p class="cab__text">Заявок пока нет. Бесплатная диагностика покажет уровень и подходящую группу.</p>' +
        '<button class="primary" data-sheet="signup">Записаться на диагностику</button>' +
        "</div>";
      return;
    }
    box.innerHTML =
      '<div class="cab__card">' +
      '<h3 class="cab__title">Мои заявки</h3>' +
      '<div class="kv-list">' +
      (lead.date ? kvRow("Дата", lead.date) : "") +
      (lead.program ? kvRow("Программа", lead.program) : "") +
      (lead.branch ? kvRow("Филиал", lead.branch) : "") +
      kvRow("Статус", lead.status) +
      "</div></div>";
  }

  function renderNext(action, schedule) {
    var box = $("#cab-next");
    if (!action) {
      box.innerHTML = "";
      return;
    }
    var cta;
    if (action.kind === "route") {
      var branch = branchInfo((state.cabinet.lead && state.cabinet.lead.branch) || "");
      cta = branch && (branch.maps || branch.address)
        ? '<a class="primary primary--glow cab__cta" target="_blank" rel="noopener" href="' +
          esc(branch.maps || "https://yandex.ru/maps/?text=" + encodeURIComponent(branch.address)) + '">' + esc(action.cta) + "</a>"
        : '<button class="primary primary--glow cab__cta" data-cab-ask-route>' + esc(action.cta) + "</button>";
    } else if (action.kind === "ask_teacher") {
      cta = '<button class="primary primary--glow cab__cta" data-cab-ask-teacher>' + esc(action.cta) + "</button>";
    } else {
      cta = '<button class="primary primary--glow cab__cta" data-sheet="' + esc(action.sheet || "quiz") + '">' + esc(action.cta) + "</button>";
    }
    box.innerHTML =
      '<div class="cab__card cab__card--next">' +
      '<h3 class="cab__title">Что дальше</h3>' +
      '<p class="cab__next-title">' + esc(action.title) + "</p>" +
      '<p class="cab__text">' + esc(action.text) + "</p>" +
      cta +
      "</div>";
    var teacher = $("[data-cab-ask-teacher]", box);
    if (teacher) {
      teacher.addEventListener("click", function () {
        askInChat("Вопрос педагогу: ");
      });
    }
    var route = $("[data-cab-ask-route]", box);
    if (route) {
      route.addEventListener("click", function () {
        askInChat("Как добраться до филиала?");
      });
    }
  }

  /** Чат с готовым вопросом: переход в раздел «Фокси» и текст в поле ввода. */
  function askInChat(text) {
    goTab("chat");
    var input = $("#chat-input");
    if (input) {
      input.value = text;
      input.focus();
    }
  }

  /* ------------------------------------------------------- карточка ребёнка */

  function buildChildEdit(box) {
    var child = currentChild();
    var levels = [""].concat(LEVEL_ORDER);
    box.innerHTML =
      '<form class="form" id="child-form" novalidate>' +
      '<label class="field"><span class="field__label">Имя</span>' +
      '<input name="name" type="text" required maxlength="120" value="' + esc(child ? child.name : "") + '" /></label>' +
      '<label class="field"><span class="field__label">Возраст</span>' +
      '<input name="age" type="text" maxlength="20" placeholder="например, 8 лет" value="' + esc(child ? child.age : "") + '" /></label>' +
      '<label class="field"><span class="field__label">Класс</span>' +
      '<input name="grade" type="text" maxlength="20" placeholder="например, 3" value="' + esc(child ? child.grade : "") + '" /></label>' +
      '<label class="field"><span class="field__label">Уровень</span>' +
      '<select name="level">' +
      levels
        .map(function (level) {
          return (
            '<option value="' + esc(level) + '"' +
            (child && child.level === level ? " selected" : "") + ">" +
            (level ? esc(level) : "пока не определён") + "</option>"
          );
        })
        .join("") +
      "</select></label>" +
      '<label class="field"><span class="field__label">Программа</span>' +
      '<input name="program" type="text" maxlength="160" value="' + esc(child ? child.program : "") + '" /></label>' +
      '<p class="status" id="child-status"></p>' +
      '<button class="primary primary--glow" type="submit">Сохранить</button>' +
      "</form>";

    on("#child-form", "submit", function (event) {
      event.preventDefault();
      var form = event.target;
      var body = {
        name: form.name.value.trim(),
        age: form.age.value.trim(),
        grade: form.grade.value.trim(),
        level: form.level.value,
        program: form.program.value.trim(),
      };
      if (child) body.id = child.id;
      if (!body.name) {
        $("#child-status").textContent = "Укажите имя";
        return;
      }
      var status = $("#child-status");
      status.textContent = "Сохраняю…";
      postJSON("/api/miniapp/cabinet/child", body)
        .then(function (data) {
          if (!data.ok) throw new Error(data.error || "Не сохранилось");
          if (state.cabinet) state.cabinet.children = data.children;
          if (!child && data.children && data.children.length) {
            state.activeChild = data.children.length - 1;
          }
          haptic("success");
          mascot("success");
          toast("Сохранено");
          closeSheet();
          if (state.tab === "profile") loadCabinet();
        })
        .catch(function (err) {
          status.textContent = err.message || "Не удалось сохранить. Попробуйте ещё раз.";
        });
    });
  }

  /* ------------------------------------------------------------- появление */

  function armReveals() {
    var blocks = all(".reveal");
    if (!("IntersectionObserver" in window)) {
      blocks.forEach(function (block) {
        block.classList.add("is-in");
      });
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px" }
    );
    blocks.forEach(function (block) {
      block.classList.add("is-armed");
      observer.observe(block);
    });
  }

  /* ------------------------------------------------------------- загрузка */

  function loadInfo() {
    return request("/api/miniapp/info")
      .then(function (data) {
        state.info = data;
        state.access = data.access || null;
        if (state.access && state.access.display_name) {
          $("#greeting-title").textContent = "Здравствуйте, " + state.access.display_name;
          $("#greeting-sub").textContent = "Чем помочь сегодня?";
        }
        renderHome();
        if (state.tab === "programs") renderCatalog();
        if (state.tab === "team") renderTeam();
      })
      .catch(function () {
        $("#offline").hidden = false;
        toast("Не удалось загрузить данные школы");
      });
  }

  function applyTheme() {
    if (!bridge) return;
    // Приложение светлое всегда: тема клиента делала экран тёмным и
    // нечитаемым, поэтому её мы намеренно не копируем.
    document.documentElement.style.colorScheme = "light";
  }

  /** Жидкие чернила в шапке. Необязательны: без WebGL и при выключенной
   *  анимации остаётся градиент, и это нормальный вид шапки. */
  function startFluid() {
    var canvas = $("#fluid");
    if (!canvas || typeof window.fluidSimulation !== "function") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    try {
      window.fluidSimulation(canvas);
    } catch (e) {
      console.warn("[foxi] чернила не запустились", e);
    }
  }

  function bind() {
    all("[data-tab-go]").forEach(function (button) {
      button.addEventListener("click", function () {
        goTab(button.dataset.tabGo);
      });
    });

    // Нажатие на кнопку меню бьёт всплеск чернил в шапке: интерфейс и
    // фон — одно целое, а не картинка и кнопки поверх неё.
    document.addEventListener("pointerdown", function (event) {
      if (!event.target || !event.target.closest) return;
      if (event.target.closest(".qa, .pulse, .dock__btn, .cab__card, .cab__kid")) {
        if (typeof window.foxiSplash === "function") window.foxiSplash(1);
      }
    }, { passive: true });

    // Лист открывает любая кнопка с data-sheet, включая появившиеся позже:
    // слушатель один на документ, а не по кнопке.
    document.addEventListener("click", function (event) {
      var target = event.target;
      if (!target || !target.closest) return;
      if (target.closest("[data-sheet-close]")) {
        closeSheet();
        return;
      }
      var opener = target.closest("[data-sheet]");
      if (opener) openSheet(opener.dataset.sheet);
    });

    all(".chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        all(".chip").forEach(function (other) {
          other.classList.toggle("is-active", other === chip);
        });
        state.ageFilter = chip.dataset.agefilter;
        haptic("light");
        renderCatalog();
      });
    });

    on("#chat-form", "submit", sendChat);

    // Свайп вниз по листу закрывает его — жест, а не только кнопка.
    var panel = $(".sheet__panel");
    var startY = null;
    on(panel, "touchstart", function (event) {
      startY = event.touches[0].clientY;
    }, { passive: true });
    on(panel, "touchmove", function (event) {
      if (startY === null) return;
      var delta = event.touches[0].clientY - startY;
      if (delta > 0) panel.style.transform = "translateY(" + delta + "px)";
    }, { passive: true });
    on(panel, "touchend", function (event) {
      var delta = event.changedTouches[0].clientY - (startY || 0);
      panel.style.transform = "";
      startY = null;
      if (delta > 90) closeSheet();
    });

    window.addEventListener("online", function () {
      $("#offline").hidden = true;
      loadInfo();
    });
    window.addEventListener("offline", function () {
      $("#offline").hidden = false;
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSheet();
    });
  }

  function start() {
    if (bridge) {
      // Оба моста умеют ready/expand, но не обязаны — вызываем осторожно.
      try {
        if (bridge.ready) bridge.ready();
        if (bridge.expand) bridge.expand();
        if (bridge.onEvent) bridge.onEvent("themeChanged", applyTheme);
      } catch (e) {
        /* мост урезан — приложение работает и так */
      }
      applyTheme();
      try {
        if (bridge.BackButton && bridge.BackButton.onClick) {
          bridge.BackButton.onClick(function () {
            if (state.sheet) closeSheet();
            else goTab("home");
          });
        }
      } catch (e) {
        /* старый клиент */
      }
    }
    startFluid();
    startPhrases();
    state.me = recall("me") || null;
    var offline = $("#offline");
    if (offline && !navigator.onLine) offline.hidden = false;
    try {
      bind();
    } catch (e) {
      // Витрина важнее интерактива: даже если часть подписок не встала,
      // человек должен увидеть школу, а не пустой экран.
      console.warn("[foxi] часть обработчиков не подключилась", e);
    }
    renderPulse();
    loadInfo();
    mascot("greet");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
