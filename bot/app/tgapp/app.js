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

  var tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
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
    scroll: {},
  };

  /* ---------------------------------------------------------------- утилиты */

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function all(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  /** Экранирование: данные приходят из базы знаний и от LLM — в innerHTML их
   *  вставлять без экранирования нельзя. */
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  /** Событие для трёхмерного маскота: он живёт в своём модуле. */
  function mascot(event) {
    document.dispatchEvent(new CustomEvent("foxi:" + event));
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
    if (name === "profile") loadProfile();
    if (name === "chat") greetInChat();
  }

  /* ---------------------------------------------------------------- листы */

  var SHEETS = {
    quiz: { title: "Тест уровня", build: buildQuiz },
    picker: { title: "Подбор курса", build: buildPicker },
    signup: { title: "Запись на занятие", build: buildSignup },
    homework: { title: "Помощь с домашкой", build: buildHomework },
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
    if (!tg) return;
    try {
      if (state.sheet || state.tab !== "home") tg.BackButton.show();
      else tg.BackButton.hide();
      tg.MainButton.hide();
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

    var progress = (quiz.index / quiz.questions.length) * 100;
    box.innerHTML =
      '<div class="quiz">' +
      '<div class="quiz__bar"><span style="width:' + progress + '%"></span></div>' +
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
        quiz.answers[question.id] = Number(button.dataset.answer);
        button.classList.add("is-picked");
        haptic("light");
        setTimeout(function () {
          quiz.index += 1;
          renderQuizStep(box);
        }, 180);
      });
    });
  }

  function finishQuiz(box) {
    box.innerHTML = '<div class="skeleton"></div>';
    postJSON("/api/miniapp/level-test", { answers: state.quiz.answers })
      .then(function (data) {
        var result = data.result;
        if (!result) throw new Error("нет результата");

        state.me = Object.assign({}, state.me, { level: result.level });
        remember("me", state.me);
        renderPulse();
        haptic("success");
        mascot("success");
        celebrate();

        box.innerHTML =
          '<div class="result">' +
          '<p class="result__label">Ваш уровень</p>' +
          '<p class="result__level">' + esc(result.level) + "</p>" +
          '<p class="result__title">' + esc(result.title) + "</p>" +
          '<p class="result__score">Верно ' + result.correct + " из " + result.total + "</p>" +
          '<p class="result__text">' + esc(result.text) + "</p>" +
          '<p class="result__note">' + esc(result.disclaimer) + "</p>" +
          '<button class="primary primary--glow" data-sheet="signup">Записаться на диагностику</button>' +
          '<button class="ghost" data-sheet="picker">Подобрать программу</button>' +
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
    form.append("photo", state.homeworkFile);
    form.append("note", $("#hw-note").value.trim());

    request("/api/miniapp/homework", { method: "POST", body: form, timeout: 90000 })
      .then(function (data) {
        if (data.__status === 403) {
          status.textContent = data.error || "Раздел откроется после регистрации.";
          return;
        }
        if (data.reply) {
          status.hidden = true;
          answer.hidden = false;
          answer.textContent = data.reply;
          haptic("success");
        } else {
          status.textContent = data.error || "Не получилось разобрать задание.";
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
    box.innerHTML = (state.info.branches || [])
      .slice(0, 2)
      .map(function (b) {
        return (
          '<article class="card">' +
          '<h3 class="card__title">' + esc(b.name) + "</h3>" +
          '<p class="card__text">' + esc(b.address || "") + "</p>" +
          (b.work_hours ? '<p class="card__text">' + esc(b.work_hours) + "</p>" : "") +
          "</article>"
        );
      })
      .join("");
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
            '<span class="person__avatar" aria-hidden="true">' +
            esc(String(person.name).slice(0, 1)) + "</span>" +
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

  function loadProfile() {
    var box = $("#profile");
    if (!inTelegram()) {
      box.innerHTML =
        '<p class="empty">Кабинет открывается из чата с ботом в Telegram — там приложение знает, кто вы.</p>';
      renderBranches();
      return;
    }
    box.innerHTML = '<div class="skeleton"></div>';
    request("/api/miniapp/profile")
      .then(function (data) {
        if (data.__status === 403 || (data.access && data.access.locked)) {
          box.innerHTML =
            '<p class="empty">' +
            esc((data.access && data.access.message) || "Кабинет откроется после регистрации в чате с ботом.") +
            "</p>";
          renderBranches();
          return;
        }
        state.profile = data;
        var rows = [
          ["Родитель", data.fio_parent],
          ["Ребёнок", data.fio_child],
          ["Возраст", data.age],
          ["Телефон", data.phone],
          ["Филиал", data.branch],
          ["Программа", data.course],
        ];
        if (state.me && state.me.level) rows.push(["Уровень по тесту", state.me.level]);
        box.innerHTML =
          rows
            .filter(function (row) {
              return row[1];
            })
            .map(function (row) {
              return (
                '<div class="kv"><span class="kv__k">' + esc(row[0]) + "</span>" +
                '<span class="kv__v">' + esc(row[1]) + "</span></div>"
              );
            })
            .join("") || '<p class="empty">Профиль пока пустой.</p>';
        renderBranches();
      })
      .catch(function () {
        box.innerHTML = '<p class="empty">Не удалось загрузить профиль.</p>';
      });
  }

  function renderBranches() {
    var box = $("#branches");
    if (!state.info) return;
    box.innerHTML = (state.info.branches || [])
      .map(function (b) {
        return (
          '<article class="card">' +
          '<h3 class="card__title">' + esc(b.name) + "</h3>" +
          '<p class="card__text">' +
          (b.maps
            ? '<a href="' + esc(b.maps) + '" target="_blank" rel="noopener">' + esc(b.address) + "</a>"
            : esc(b.address)) +
          "</p>" +
          (b.phone
            ? '<p class="card__text"><a href="tel:' + esc(b.phone_tel || b.phone) + '">' +
              esc(b.phone) + "</a></p>"
            : "") +
          "</article>"
        );
      })
      .join("");
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
    if (!tg) return;
    // Приложение светлое всегда: тема клиента делала экран тёмным и
    // нечитаемым, поэтому её мы намеренно не копируем.
    document.documentElement.style.colorScheme = "light";
  }

  function bind() {
    all("[data-tab-go]").forEach(function (button) {
      button.addEventListener("click", function () {
        goTab(button.dataset.tabGo);
      });
    });

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

    $("#chat-form").addEventListener("submit", sendChat);

    // Свайп вниз по листу закрывает его — жест, а не только кнопка.
    var panel = $(".sheet__panel");
    var startY = null;
    panel.addEventListener("touchstart", function (event) {
      startY = event.touches[0].clientY;
    }, { passive: true });
    panel.addEventListener("touchmove", function (event) {
      if (startY === null) return;
      var delta = event.touches[0].clientY - startY;
      if (delta > 0) panel.style.transform = "translateY(" + delta + "px)";
    }, { passive: true });
    panel.addEventListener("touchend", function (event) {
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
    if (tg) {
      tg.ready();
      tg.expand();
      applyTheme();
      tg.onEvent("themeChanged", applyTheme);
      try {
        tg.BackButton.onClick(function () {
          if (state.sheet) closeSheet();
          else goTab("home");
        });
      } catch (e) {
        /* старый клиент */
      }
    }
    state.me = recall("me") || null;
    if (!navigator.onLine) $("#offline").hidden = false;
    bind();
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
