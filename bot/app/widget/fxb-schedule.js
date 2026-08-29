(() => {
  if (window.__fxbScheduleLoaded) return;
  window.__fxbScheduleLoaded = true;

  const script = document.currentScript || Array.from(document.scripts).find((n) =>
    typeof n.src === "string" && n.src.includes("/widget/fxb-schedule.js"));
  const apiBase = script && script.src ? new URL(script.src).origin : window.location.origin;
  const rootEl = document.getElementById("fxb-schedule");
  if (!rootEl) return;

  const state = {
    filials: [], groups: [], lessons: [], freshness: null,
    filialId: "", teacher: "", level: "", day: "",
    loading: true, error: "",
    bookingFor: null, sending: false, done: null, alternatives: [],
    paying: false, payInfo: null,
  };

  const css = document.createElement("style");
  css.textContent = `
    #fxb-schedule{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;color:#0f172a}
    #fxb-schedule *{box-sizing:border-box}
    .fxs-filters{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 8px}
    .fxs-filters select{appearance:none;padding:12px 42px 12px 18px;border-radius:999px;border:1.5px solid #e9e4f8;background:linear-gradient(180deg,#faf8ff,#f4f0fd) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%237c3aed' stroke-width='2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E") no-repeat right 16px center;font-family:inherit;font-size:14px;font-weight:600;color:#3b2d66;min-height:48px;cursor:pointer;flex:1;min-width:150px;box-shadow:0 2px 10px rgba(124,58,237,.07);transition:border-color .15s ease,box-shadow .15s ease,transform .15s ease}
    .fxs-filters select:hover{border-color:#c4b5fd;box-shadow:0 4px 16px rgba(124,58,237,.13);transform:translateY(-1px)}
    .fxs-filters select:focus{outline:none;border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.18)}
    .fxs-filters select.fxs-active{background:linear-gradient(180deg,#7c3aed,#5b21b6);color:#fff;border-color:transparent}
    .fxs-filters select.fxs-active{background-image:linear-gradient(180deg,#7c3aed,#5b21b6),url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23ffffff' stroke-width='2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:center,right 16px center}
    .fxs-count{font-size:13px;color:#94a3b8;margin:0 0 16px}
    .fxs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
    .fxs-card{background:#fff;border:1px solid #ececf4;border-radius:20px;padding:20px;display:flex;flex-direction:column;gap:10px;box-shadow:0 6px 24px rgba(15,23,42,.05);transition:transform .18s ease,box-shadow .18s ease}
    .fxs-card:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(15,23,42,.09)}
    .fxs-card h3{margin:0;font-size:16.5px;line-height:1.35;letter-spacing:-0.01em}
    .fxs-tags{display:flex;gap:6px;flex-wrap:wrap}
    .fxs-tag{font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;background:#f1f5f9;color:#475569}
    .fxs-tag.level{background:#ede9fe;color:#6d28d9}
    .fxs-tag.course{background:#fef3c7;color:#92400e}
    .fxs-tag.event{background:#fce7f3;color:#be185d}
    .fxs-tag.teacher{background:#eff6ff;color:#1d4ed8}
    .fxs-meta{font-size:14px;color:#64748b;display:flex;flex-direction:column;gap:4px}
    .fxs-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
    .fxs-price{font-size:15px;font-weight:700;color:#0f172a}
    .fxs-slots{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;padding:5px 12px;border-radius:999px;width:fit-content}
    .fxs-slots.ok{background:#ecfdf5;color:#047857}
    .fxs-slots.low{background:#fff7ed;color:#c2410c}
    .fxs-slots.none{background:#f1f5f9;color:#64748b}
    .fxs-btn{margin-top:auto;border:none;border-radius:14px;padding:13px 18px;font-size:15px;font-weight:600;cursor:pointer;background:linear-gradient(180deg,#7c3aed,#5b21b6);color:#fff;min-height:48px;transition:filter .15s ease}
    .fxs-btn:hover{filter:brightness(1.08)}
    .fxs-btn:disabled{opacity:.55;cursor:default}
    .fxs-btn.ghost{background:#f1f5f9;color:#0f172a}
    .fxs-note{margin-top:14px;font-size:13px;color:#94a3b8}
    .fxs-empty,.fxs-error,.fxs-loading{padding:40px 24px;text-align:center;color:#64748b;background:#fff;border:1px dashed #e2e8f0;border-radius:20px}
    .fxs-error button{margin-top:12px}
    .fxs-skel{height:170px;border-radius:20px;background:linear-gradient(90deg,#f1f5f9 25%,#e8edf5 50%,#f1f5f9 75%);background-size:400% 100%;animation:fxs-shimmer 1.3s infinite}
    @keyframes fxs-shimmer{0%{background-position:100% 0}100%{background-position:0 0}}
    .fxs-overlay{position:fixed;inset:0;background:rgba(15,23,42,.5);z-index:2147483000;display:flex;align-items:flex-end;justify-content:center;padding:0}
    @media(min-width:640px){.fxs-overlay{align-items:center;padding:24px}}
    .fxs-modal{background:#fff;border-radius:24px 24px 0 0;width:100%;max-width:480px;max-height:92vh;overflow:auto;padding:24px}
    @media(min-width:640px){.fxs-modal{border-radius:24px}}
    .fxs-modal h3{margin:0 0 4px;font-size:19px}
    .fxs-modal .fxs-sub{font-size:14px;color:#64748b;margin-bottom:16px}
    .fxs-field{margin-bottom:12px}
    .fxs-field label{display:block;font-size:13px;font-weight:600;margin-bottom:6px;color:#334155}
    .fxs-field input{width:100%;padding:13px 14px;border-radius:14px;border:1px solid #e2e8f0;font-size:16px;min-height:48px}
    .fxs-field input:focus{outline:2px solid #7c3aed;outline-offset:-1px;border-color:transparent}
    .fxs-field .fxs-err{color:#dc2626;font-size:13px;margin-top:4px;display:none}
    .fxs-field.invalid input{border-color:#dc2626}
    .fxs-field.invalid .fxs-err{display:block}
    .fxs-actions{display:flex;gap:10px;margin-top:18px}
    .fxs-actions .fxs-btn{flex:1;margin-top:0}
    .fxs-success{text-align:center;padding:20px 0}
    .fxs-success .fxs-ico{font-size:44px;margin-bottom:10px}
    .fxs-alt{margin-top:14px;display:flex;flex-direction:column;gap:8px}
    .fxs-alt button{text-align:left;border:1px solid #e2e8f0;background:#fff;border-radius:14px;padding:12px 14px;font-size:14px;cursor:pointer}
    .fxs-alt button:hover{border-color:#7c3aed}
    .fxs-payinfo{background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:12px 14px;font-size:14px;color:#334155;margin-top:4px}
    .fxs-sbp{display:block;text-align:center;text-decoration:none;border:none;border-radius:16px;padding:16px 18px;font-size:17px;font-weight:700;color:#fff;min-height:56px;background:linear-gradient(135deg,#0aa75d,#0879c4);box-shadow:0 8px 24px rgba(10,167,93,.3);cursor:pointer;transition:filter .15s ease,transform .15s ease;margin-top:6px}
    .fxs-sbp:hover{filter:brightness(1.07);transform:translateY(-1px)}
    .fxs-qr{display:flex;justify-content:center;margin:14px 0 6px}
    .fxs-qr svg{width:176px;height:176px;border-radius:12px}
    .fxs-qrhint{text-align:center;font-size:12.5px;color:#94a3b8;margin-bottom:8px}
    .fxs-dates{display:flex;flex-direction:column;gap:8px;max-height:216px;overflow:auto;padding-right:2px}
    .fxs-date{display:flex;align-items:center;gap:10px;padding:11px 14px;border:1.5px solid #e2e8f0;border-radius:14px;font-size:14.5px;color:#334155;cursor:pointer;transition:border-color .15s ease,background .15s ease}
    .fxs-date:hover{border-color:#c4b5fd}
    .fxs-date input{accent-color:#7c3aed;width:18px;height:18px;flex-shrink:0}
    .fxs-date:has(input:checked){border-color:#7c3aed;background:#f5f3ff;font-weight:600;color:#3b2d66}
    .fxs-when{font-size:14.5px;color:#334155;background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:12px 14px;margin-bottom:12px}
    .fxs-field input[type=date]{color-scheme:light}
    .fxs-link{display:block;text-align:center;font-size:14.5px;font-weight:600;color:#7c3aed;text-decoration:none;padding:12px;border-radius:12px;border:1.5px solid #ede9fe;background:#faf8ff;margin-top:8px}
    .fxs-link:hover{border-color:#c4b5fd}
    @media(prefers-reduced-motion:reduce){.fxs-skel{animation:none}.fxs-card{transition:none}}
  `;
  document.head.appendChild(css);

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

  const fmtWhen = (lesson) => {
    if (!lesson) return "";
    const d = lesson.starts_at ? new Date(lesson.starts_at) : null;
    if (!d || isNaN(d)) return lesson.date || "";
    const days = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
    const months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${days[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]} · ${hh}:${mm}`;
  };

  const fmtAgo = (iso) => {
    if (!iso) return "";
    const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    if (mins < 1) return "только что";
    if (mins < 60) return `${mins} мин назад`;
    const h = Math.round(mins / 60);
    return `${h} ч назад`;
  };

  const fmtPrice = (rub) => `${Number(rub).toLocaleString("ru-RU")} ₽`;

  const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  const fmtPeriod = (g) => {
    if (!g.period_start || !g.period_end) return "";
    const d0 = new Date(g.period_start), d1 = new Date(g.period_end);
    if (isNaN(d0) || isNaN(d1)) return "";
    const spanDays = (d1 - d0) / 86400000;
    if (spanDays < 45) return ""; // короткие наборы не подписываем
    const f = (d) => `${d.getDate()} ${MONTHS_SHORT[d.getMonth()]}`;
    return `Период: ${f(d0)} — ${f(d1)}`;
  };

  async function api(path, opts) {
    const resp = await fetch(`${apiBase}/api/platform${path}`, opts);
    const body = await resp.json().catch(() => ({}));
    return { status: resp.status, body };
  }

  /* Аналитика: fire-and-forget, ошибки сети молча игнорируем. */
  const sessionId = (() => {
    try {
      let v = sessionStorage.getItem("fxs:sid");
      if (!v) { v = Math.random().toString(36).slice(2); sessionStorage.setItem("fxs:sid", v); }
      return v;
    } catch (e) { return ""; }
  })();
  function track(event, meta) {
    try {
      fetch(`${apiBase}/api/platform/events`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event, source: "site", session_id: sessionId, meta: meta || {} }),
        keepalive: true,
      }).catch(() => {});
    } catch (e) { /* аналитика не должна ломать виджет */ }
  }

  async function load() {
    state.loading = true; state.error = "";
    render();
    try {
      const params = state.filialId ? `?filial_id=${state.filialId}` : "";
      const [f, g, s] = await Promise.all([
        api("/filials"), api(`/groups${params}`),
        api(`/schedule?days=60${state.filialId ? `&filial_id=${state.filialId}` : ""}`),
      ]);
      state.filials = f.body.data || [];
      state.groups = g.body.data || [];
      state.lessons = s.body.data || [];
      state.freshness = s.body.freshness || null;
      state.loading = false;
      track("schedule_open", { groups: state.groups.length });
    } catch (e) {
      state.loading = false;
      state.error = "Не удалось загрузить расписание. Мы попробуем обновить данные.";
    }
    render();
  }

  function lessonsFor(groupId) {
    const today = new Date().toISOString().slice(0, 10);
    return state.lessons
      .filter((l) => l.group_id === groupId && (l.starts_at || l.date) >= today)
      .sort((a, b) => String(a.starts_at || a.date).localeCompare(String(b.starts_at || b.date)));
  }

  function lessonDay(l) {
    const d = l.starts_at ? new Date(l.starts_at) : null;
    return d && !isNaN(d) ? d.getDay() : null;
  }

  function nextLessonFor(groupId) {
    const all = lessonsFor(groupId);
    if (state.day === "") return all[0] || null;
    return all.find((l) => lessonDay(l) === Number(state.day)) || null;
  }

  function visibleGroups() {
    return state.groups
      .filter((g) => {
        if (state.teacher && (g.teacher || "") !== state.teacher) return false;
        if (state.level && (g.level || "") !== state.level) return false;
        if (state.day !== "" && !lessonsFor(g.id).some((l) => lessonDay(l) === Number(state.day))) return false;
        return true;
      })
      .sort((a, b) =>
        (a.level_rank ?? 99) - (b.level_rank ?? 99) ||
        (a.teacher || "").localeCompare(b.teacher || "", "ru") ||
        (a.caption || "").localeCompare(b.caption || "", "ru"));
  }

  function slotsBadge(g) {
    if (g.free_slots === null || g.free_slots === undefined)
      return `<span class="fxs-slots none">уточните места</span>`;
    if (g.free_slots <= 0) return `<span class="fxs-slots none">мест нет</span>`;
    const cls = g.low_availability ? "low" : "ok";
    const word = g.free_slots === 1 ? "место" : g.free_slots < 5 ? "места" : "мест";
    return `<span class="fxs-slots ${cls}">${g.free_slots} ${word}</span>`;
  }

  function opts(values, current, allLabel) {
    return [`<option value="">${allLabel}</option>`]
      .concat(values.map((v) =>
        `<option value="${esc(v.v)}" ${String(v.v) === String(current) ? "selected" : ""}>${esc(v.label)}</option>`)).join("");
  }

  function render() {
    if (state.loading) {
      rootEl.innerHTML = `<div class="fxs-grid">${'<div class="fxs-skel"></div>'.repeat(6)}</div>`;
      return;
    }
    if (state.error) {
      rootEl.innerHTML = `<div class="fxs-error">${esc(state.error)}<br>
        <button class="fxs-btn" data-fxs="retry">Повторить</button></div>`;
      return;
    }
    const teachers = [...new Set(state.groups.map((g) => g.teacher).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
    const levels = [...new Set(state.groups.map((g) => g.level).filter(Boolean))]
      .sort((a, b) => { const r = (x) => { const g = state.groups.find((gg) => gg.level === x); return g ? g.level_rank : 99; }; return r(a) - r(b); });
    const dayNames = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
    const days = [1, 2, 3, 4, 5, 6, 0].map((d) => ({ v: d, label: dayNames[d][0].toUpperCase() + dayNames[d].slice(1) }));
    const groups = visibleGroups();
    const cards = groups.map((g) => {
      const next = nextLessonFor(g.id);
      const full = g.free_slots !== null && g.free_slots <= 0;
      const period = fmtPeriod(g);
      const tags = [
        g.is_event ? `<span class="fxs-tag event">🎉 Мероприятие</span>` : "",
        g.course ? `<span class="fxs-tag course">${esc(g.course)}</span>` : "",
        g.level ? `<span class="fxs-tag level">${esc(g.level)}</span>` : "",
        g.teacher ? `<span class="fxs-tag teacher">👩‍🏫 ${esc(g.teacher)}</span>` : "",
        g.duration_min ? `<span class="fxs-tag">⏱ ${g.duration_min} мин</span>` : "",
      ].join("");
      const effPrice = g.is_event ? g.event_price_rub : g.trial_price_rub;
      const priceLabel = g.is_event ? "Участие" : "Пробное";
      const price = effPrice
        ? `<span class="fxs-price">${priceLabel} · ${fmtPrice(effPrice)}</span>` : "";
      const btnLabel = full ? "Мест нет"
        : next ? (effPrice
            ? (g.is_event ? `Оплатить участие · ${fmtPrice(effPrice)}` : `Записаться · ${fmtPrice(effPrice)}`)
            : (g.is_event ? "Записаться на мероприятие" : "Записаться на пробное"))
        : "Нет занятий";
      return `<div class="fxs-card">
        <h3>${esc(g.caption)}</h3>
        ${tags ? `<div class="fxs-tags">${tags}</div>` : ""}
        <div class="fxs-meta">
          <span>📍 ${esc(g.filial.caption || "")}</span>
          ${next ? `<span>🗓 Ближайшее: ${esc(fmtWhen(next))}</span>` : ""}
          ${period ? `<span>📅 ${esc(period)}</span>` : ""}
        </div>
        <div class="fxs-row">${slotsBadge(g)}${price}</div>
        <button class="fxs-btn" data-fxs="book" data-group="${g.id}" data-lesson="${next ? next.lesson_id : ""}" ${full || !next ? "disabled" : ""}>${btnLabel}</button>
      </div>`;
    }).join("");
    rootEl.innerHTML = `
      <div class="fxs-filters">
        <select class="${state.filialId ? "fxs-active" : ""}" data-fxs="filial" aria-label="Филиал">${opts(state.filials.map((f) => ({ v: f.id, label: f.caption })), state.filialId, "📍 Все филиалы")}</select>
        <select class="${state.teacher ? "fxs-active" : ""}" data-fxs="teacher" aria-label="Педагог">${opts(teachers.map((t) => ({ v: t, label: t })), state.teacher, "👩‍🏫 Все педагоги")}</select>
        <select class="${state.level ? "fxs-active" : ""}" data-fxs="level" aria-label="Уровень">${opts(levels.map((l) => ({ v: l, label: l })), state.level, "🎯 Все уровни")}</select>
        <select class="${state.day !== "" ? "fxs-active" : ""}" data-fxs="day" aria-label="День недели">${opts(days, state.day, "🗓 Любой день")}</select>
      </div>
      <p class="fxs-count">${groups.length ? `Групп: ${groups.length}` : ""}</p>
      ${groups.length ? `<div class="fxs-grid">${cards}</div>`
        : `<div class="fxs-empty">По выбранным условиям групп не нашлось. Попробуйте изменить фильтры или напишите нам — подберём вариант.</div>`}
      ${state.freshness && state.freshness.groups_synced_at
        ? `<div class="fxs-note">Данные о местах обновлены ${fmtAgo(state.freshness.groups_synced_at)}</div>` : ""}`;
  }

  function openBooking(groupId, lessonId) {
    track("group_view", { group_id: Number(groupId) || 0 });
    const g = state.groups.find((x) => String(x.id) === String(groupId));
    const dates = lessonsFor(Number(groupId)).slice(0, 8);
    const lesson = state.lessons.find((l) => String(l.lesson_id) === String(lessonId)) || dates[0] || null;
    state.bookingFor = { groupId, lessonId: lesson ? lesson.lesson_id : "", group: g, lesson, dates };
    state.done = null; state.alternatives = []; state.payInfo = null; state.paying = false;
    renderModal();
  }

  function renderModal() {
    closeModal(false);
    const { group, lesson } = state.bookingFor;
    const ov = document.createElement("div");
    ov.className = "fxs-overlay";
    ov.id = "fxs-overlay";
    if (state.done === "confirmed" || state.done === "duplicate") {
      ov.innerHTML = `<div class="fxs-modal"><div class="fxs-success">
        <div class="fxs-ico">🎉</div><h3>Вы записаны!</h3>
        <p class="fxs-sub">Оплата подтверждена, место закреплено за вами. Мы свяжемся накануне занятия.</p>
        <button class="fxs-btn" data-fxs="close">Хорошо</button></div></div>`;
    } else if (state.done === "pay_tbank") {
      const p = state.payInfo || {};
      ov.innerHTML = `<div class="fxs-modal" role="dialog" aria-modal="true" aria-label="Оплата">
        <h3>Оплата — ${fmtPrice(p.amount_rub)}</h3>
        <p class="fxs-sub">Место зарезервировано за вами. Оплатите — и запись подтвердится автоматически, обычно это занимает несколько секунд.</p>
        ${p.sbp_url ? `<a class="fxs-sbp" href="${esc(p.sbp_url)}" target="_blank" rel="noopener">Оплатить по СБП</a>` : ""}
        ${p.sbp_qr_svg ? `<div class="fxs-qr">${p.sbp_qr_svg}</div><div class="fxs-qrhint">Или наведите камеру телефона — откроется приложение банка</div>` : ""}
        ${p.payment_url ? `<a class="fxs-link" href="${esc(p.payment_url)}" target="_blank" rel="noopener">Оплатить картой онлайн</a>` : ""}
        <div class="fxs-actions"><button class="fxs-btn ghost" data-fxs="close">Закрыть</button></div></div>`;
    } else if (state.done === "pending_payment") {
      ov.innerHTML = `<div class="fxs-modal"><div class="fxs-success">
        <div class="fxs-ico">⏳</div><h3>Проверяем оплату…</h3>
        <p class="fxs-sub">Это обычно занимает до минуты. Как только платёж подтвердится — пришлём сообщение и закрепим место.</p>
        <button class="fxs-btn ghost" data-fxs="close">Закрыть</button></div></div>`;
    } else if (state.done === "slot_unavailable") {
      const alts = state.alternatives.map((a) =>
        `<button data-fxs="alt" data-group="${a.group_id}">${esc(a.caption)} — ${esc(a.filial)}${a.free_slots !== null ? ` (${a.free_slots} мест)` : ""}</button>`).join("");
      ov.innerHTML = `<div class="fxs-modal"><h3>Место только что заняли</h3>
        <p class="fxs-sub">Ничего страшного — вот похожие группы со свободными местами:</p>
        <div class="fxs-alt">${alts || "<p>Свободных альтернатив сейчас нет — оставьте заявку, и мы подберём вариант.</p>"}</div>
        <div class="fxs-actions"><button class="fxs-btn ghost" data-fxs="close">Закрыть</button></div></div>`;
    } else {
      const price = group && (group.is_event ? group.event_price_rub : group.trial_price_rub);
      const dates = state.bookingFor.dates || [];
      const selId = String(state.bookingFor.lessonId);
      const dateOpts = dates.map((l) => `
        <label class="fxs-date"><input type="radio" name="lesson_id" value="${l.lesson_id}" ${String(l.lesson_id) === selId ? "checked" : ""}>
          <span>${esc(fmtWhen(l))}</span></label>`).join("");
      const today = new Date().toISOString().slice(0, 10);
      ov.innerHTML = `<div class="fxs-modal" role="dialog" aria-modal="true" aria-label="Запись на пробное занятие">
        <h3>${group && group.is_event ? "Запись на мероприятие" : "Запись на пробное занятие"}</h3>
        <p class="fxs-sub">${esc(group ? group.caption : "")}</p>
        ${price ? `<div class="fxs-payinfo">${group && group.is_event ? "Стоимость участия" : "Стоимость пробного занятия"} — <b>${fmtPrice(price)}</b>. Оплата по СБП или картой онлайн, место закрепляется сразу после оплаты.</div>` : ""}
        <form id="fxs-form" novalidate>
          ${dates.length > 1 ? `<div class="fxs-field"><label>${group && group.is_event ? "Дата мероприятия" : "Удобная дата пробного"}</label><div class="fxs-dates">${dateOpts}</div></div>`
            : (lesson ? `<div class="fxs-when">🗓 ${esc(fmtWhen(lesson))}</div>` : "")}
          <div class="fxs-field" data-f="parent_name"><label>Имя родителя</label>
            <input name="parent_name" autocomplete="name" placeholder="Как к вам обращаться">
            <div class="fxs-err">Укажите имя</div></div>
          <div class="fxs-field" data-f="phone"><label>Номер телефона родителя</label>
            <input name="phone" type="tel" autocomplete="tel" inputmode="tel" placeholder="+7 (___) ___-__-__">
            <div class="fxs-err">Укажите корректный номер</div></div>
          <div class="fxs-field" data-f="child_name"><label>Имя ребёнка</label>
            <input name="child_name" placeholder="Например, Маша"></div>
          <div class="fxs-field" data-f="child_birthdate"><label>Дата рождения ребёнка</label>
            <input name="child_birthdate" type="date" min="2005-01-01" max="${today}">
            <div class="fxs-err">Укажите дату рождения</div></div>
          <div class="fxs-actions">
            <button type="button" class="fxs-btn ghost" data-fxs="close">Отмена</button>
            <button type="submit" class="fxs-btn" ${state.sending ? "disabled" : ""}>${state.sending ? "Отправляем…" : price ? `Перейти к оплате · ${fmtPrice(price)}` : (group && group.is_event ? "Записаться на мероприятие" : "Записаться")}</button>
          </div>
        </form></div>`;
      ov.querySelector("#fxs-form").addEventListener("submit", onSubmit);
      const first = ov.querySelector("input");
      if (first) setTimeout(() => first.focus(), 50);
    }
    ov.addEventListener("click", (e) => { if (e.target === ov && !state.paying) closeModal(); });
    document.body.appendChild(ov);
  }

  function closeModal(rerender = true) {
    const old = document.getElementById("fxs-overlay");
    if (old) old.remove();
    if (rerender) state.bookingFor = null;
  }

  function loadCpWidget() {
    return new Promise((resolve, reject) => {
      if (window.cp && window.cp.CloudPayments) return resolve();
      const s = document.createElement("script");
      s.src = "https://widget.cloudpayments.ru/bundles/cloudpayments.js";
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("widget_load_failed"));
      document.head.appendChild(s);
    });
  }

  async function pollBooking(bookingId, attempts = 15) {
    for (let i = 0; i < attempts; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const { body } = await api(`/booking/${bookingId}`);
        if (body && (body.status === "confirmed" || body.status === "duplicate")) return "confirmed";
        if (body && body.status === "failed") return "failed";
      } catch (e) { /* повторяем */ }
    }
    return "timeout";
  }

  function startTbankPayment(pay) {
    track("payment_started", { invoice_id: pay.invoice_id, provider: "tbank" });
    state.payInfo = pay;
    state.done = "pay_tbank";
    renderModal();
    // Подтверждение приходит вебхуком или опросом статуса — ждём и обновляем.
    pollBooking(pay.booking_id).then((res) => {
      if (res === "confirmed") {
        state.done = "confirmed";
        renderModal();
        load();
      }
    });
  }

  async function startCpPayment(pay) {
    state.paying = true;
    try {
      await loadCpWidget();
      // Наш модал имеет максимальный z-index и перекрыл бы форму оплаты —
      // прячем его, пока виджет CP открыт. bookingFor сохраняется.
      closeModal(false);
      const widget = new window.cp.CloudPayments();
      widget.pay("charge", {
        publicId: pay.widget.publicId,
        description: pay.widget.description,
        amount: pay.widget.amount,
        currency: pay.widget.currency,
        invoiceId: pay.widget.invoiceId,
        accountId: pay.widget.accountId,
        skin: "mini",
      }, {
        onSuccess: async () => {
          track("payment_started", { invoice_id: pay.invoice_id });
          state.done = "pending_payment";
          renderModal();
          const res = await pollBooking(state.payInfo.booking_id);
          if (res === "confirmed") {
            state.done = "confirmed";
            renderModal();
            load();
          }
          // timeout: остаёмся на экране «проверяем оплату» — честно
        },
        onFail: () => {
          state.done = null;
          state.paying = false;
          renderModal();
          alert("Оплата не прошла — деньги не списаны. Попробуйте ещё раз.");
        },
        onComplete: () => { state.paying = false; },
      });
    } catch (e) {
      state.paying = false;
      renderModal();
      alert("Не удалось загрузить платёжную форму. Проверьте интернет и попробуйте ещё раз.");
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (state.sending) return;
    const form = e.target;
    const val = (n) => (form.elements[n] ? form.elements[n].value.trim() : "");
    let ok = true;
    const mark = (name, valid) => {
      const field = form.querySelector(`[data-f="${name}"]`);
      if (field) field.classList.toggle("invalid", !valid);
      if (!valid) ok = false;
    };
    mark("parent_name", val("parent_name").length >= 2);
    mark("phone", val("phone").replace(/\D/g, "").length >= 10);
    mark("child_birthdate", /^\d{4}-\d{2}-\d{2}$/.test(val("child_birthdate")));
    if (!ok) return;

    state.sending = true; renderModal();
    const idem = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    const { status, body } = await api("/booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parent_name: val("parent_name"), phone: val("phone"),
        child_name: val("child_name"), child_birthdate: val("child_birthdate"),
        group_id: Number(state.bookingFor.groupId),
        lesson_id: Number(val("lesson_id") || state.bookingFor.lessonId),
        source: "site-schedule", idempotency_key: idem,
      }),
    });
    state.sending = false;
    if (status === 201 && body && body.status === "awaiting_payment") {
      // Платное пробное: экран оплаты активного провайдера (Т-Банк/СБП или CP)
      if (body.provider === "tbank") {
        startTbankPayment(body);
      } else {
        state.payInfo = { booking_id: body.booking_id, invoice_id: body.invoice_id, widget: body.widget };
        startCpPayment(state.payInfo);
      }
      return;
    }
    if (status === 201 || (body && body.status === "duplicate")) {
      state.done = body.status === "duplicate" ? "duplicate" : "confirmed";
      renderModal();
      load(); // обновить места после записи
    } else if (status === 409) {
      state.done = "slot_unavailable";
      state.alternatives = (body && body.alternatives) || [];
      renderModal();
    } else {
      state.done = null;
      alert((body && body.message) || "Не удалось оформить запись. Попробуйте позже.");
      renderModal();
    }
  }

  // Клики делегируем на document: модал рендерится в <body>, вне rootEl —
  // поэтому «Отмена»/«Закрыть» раньше не работали.
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-fxs]");
    if (!t) return;
    const act = t.getAttribute("data-fxs");
    if (act === "retry") load();
    if (act === "book") openBooking(t.getAttribute("data-group"), t.getAttribute("data-lesson"));
    if (act === "close") closeModal();
    if (act === "alt") {
      const gid = t.getAttribute("data-group");
      closeModal();
      load().then(() => {
        const lesson = nextLessonFor(Number(gid));
        if (lesson) openBooking(gid, lesson.lesson_id);
      });
    }
  });
  rootEl.addEventListener("change", (e) => {
    const t = e.target.closest("select[data-fxs]");
    if (!t) return;
    const kind = t.getAttribute("data-fxs");
    if (kind === "filial") { state.filialId = t.value; track("filter_used", { filial_id: t.value }); load(); return; }
    if (kind === "teacher") state.teacher = t.value;
    if (kind === "level") state.level = t.value;
    if (kind === "day") state.day = t.value;
    track("filter_used", { [kind]: t.value });
    render();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.getElementById("fxs-overlay") && !state.paying) closeModal();
  });

  load();
})();
