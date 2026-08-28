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
    filialId: "", day: "", loading: true, error: "",
    bookingFor: null, sending: false, done: null, alternatives: [],
  };

  const css = document.createElement("style");
  css.textContent = `
    #fxb-schedule{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;color:#0f172a}
    #fxb-schedule *{box-sizing:border-box}
    .fxs-filters{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 20px}
    .fxs-filters select{appearance:none;padding:12px 16px;border-radius:14px;border:1px solid #e2e8f0;background:#fff;font-size:15px;min-height:48px;cursor:pointer;flex:1;min-width:160px}
    .fxs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
    .fxs-card{background:#fff;border:1px solid #ececf4;border-radius:20px;padding:20px;display:flex;flex-direction:column;gap:10px;box-shadow:0 6px 24px rgba(15,23,42,.05);transition:transform .18s ease,box-shadow .18s ease}
    .fxs-card:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(15,23,42,.09)}
    .fxs-card h3{margin:0;font-size:17px;line-height:1.35}
    .fxs-meta{font-size:14px;color:#64748b;display:flex;flex-direction:column;gap:4px}
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
    .fxs-skel{height:150px;border-radius:20px;background:linear-gradient(90deg,#f1f5f9 25%,#e8edf5 50%,#f1f5f9 75%);background-size:400% 100%;animation:fxs-shimmer 1.3s infinite}
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
        api(`/schedule?days=21${state.filialId ? `&filial_id=${state.filialId}` : ""}`),
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

  function nextLessonFor(groupId) {
    const now = new Date().toISOString();
    const upcoming = state.lessons
      .filter((l) => l.group_id === groupId && (l.starts_at || l.date) >= now.slice(0, 10))
      .sort((a, b) => String(a.starts_at || a.date).localeCompare(String(b.starts_at || b.date)));
    return upcoming[0] || null;
  }

  function slotsBadge(g) {
    if (g.free_slots === null || g.free_slots === undefined)
      return `<span class="fxs-slots none">уточните места</span>`;
    if (g.free_slots <= 0) return `<span class="fxs-slots none">мест нет</span>`;
    const cls = g.low_availability ? "low" : "ok";
    const word = g.free_slots === 1 ? "место" : g.free_slots < 5 ? "места" : "мест";
    return `<span class="fxs-slots ${cls}">${g.free_slots} ${word}</span>`;
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
    const filialOpts = [`<option value="">Все филиалы</option>`]
      .concat(state.filials.map((f) =>
        `<option value="${f.id}" ${String(f.id) === String(state.filialId) ? "selected" : ""}>${esc(f.caption)}</option>`));
    const cards = state.groups.map((g) => {
      const next = nextLessonFor(g.id);
      const full = g.free_slots !== null && g.free_slots <= 0;
      return `<div class="fxs-card">
        <h3>${esc(g.caption)}</h3>
        <div class="fxs-meta">
          <span>📍 ${esc(g.filial.caption || "")}</span>
          ${next ? `<span>🗓 Ближайшее: ${esc(fmtWhen(next))}</span>` : ""}
        </div>
        ${slotsBadge(g)}
        <button class="fxs-btn" data-fxs="book" data-group="${g.id}" data-lesson="${next ? next.lesson_id : ""}" ${full || !next ? "disabled" : ""}>
          ${full ? "Мест нет" : next ? "Записаться на пробное" : "Нет занятий"}</button>
      </div>`;
    }).join("");
    rootEl.innerHTML = `
      <div class="fxs-filters"><select data-fxs="filial" aria-label="Филиал">${filialOpts}</select></div>
      ${state.groups.length ? `<div class="fxs-grid">${cards}</div>`
        : `<div class="fxs-empty">По выбранным условиям групп не нашлось. Попробуйте другой филиал или напишите нам — подберём вариант.</div>`}
      ${state.freshness && state.freshness.groups_synced_at
        ? `<div class="fxs-note">Данные о местах обновлены ${fmtAgo(state.freshness.groups_synced_at)}</div>` : ""}`;
  }

  function openBooking(groupId, lessonId) {
    track("group_view", { group_id: Number(groupId) || 0 });
    const g = state.groups.find((x) => String(x.id) === String(groupId));
    const lesson = state.lessons.find((l) => String(l.lesson_id) === String(lessonId));
    state.bookingFor = { groupId, lessonId, group: g, lesson };
    state.done = null; state.alternatives = [];
    renderModal();
  }

  function renderModal() {
    closeModal(false);
    const { groupId, lessonId, group, lesson } = state.bookingFor;
    const ov = document.createElement("div");
    ov.className = "fxs-overlay";
    ov.id = "fxs-overlay";
    if (state.done === "confirmed" || state.done === "duplicate") {
      ov.innerHTML = `<div class="fxs-modal"><div class="fxs-success">
        <div class="fxs-ico">🎉</div><h3>Вы записаны!</h3>
        <p class="fxs-sub">Мы свяжемся с вами для подтверждения. Если что-то пойдёт не так — позвоните нам.</p>
        <button class="fxs-btn" data-fxs="close">Хорошо</button></div></div>`;
    } else if (state.done === "slot_unavailable") {
      const alts = state.alternatives.map((a) =>
        `<button data-fxs="alt" data-group="${a.group_id}">${esc(a.caption)} — ${esc(a.filial)}${a.free_slots !== null ? ` (${a.free_slots} мест)` : ""}</button>`).join("");
      ov.innerHTML = `<div class="fxs-modal"><h3>Место только что заняли</h3>
        <p class="fxs-sub">Ничего страшного — вот похожие группы со свободными местами:</p>
        <div class="fxs-alt">${alts || "<p>Свободных альтернатив сейчас нет — оставьте заявку, и мы подберём вариант.</p>"}</div>
        <div class="fxs-actions"><button class="fxs-btn ghost" data-fxs="close">Закрыть</button></div></div>`;
    } else {
      ov.innerHTML = `<div class="fxs-modal" role="dialog" aria-modal="true" aria-label="Запись на пробное занятие">
        <h3>Запись на пробное занятие</h3>
        <p class="fxs-sub">${esc(group ? group.caption : "")}${lesson ? `<br>🗓 ${esc(fmtWhen(lesson))}` : ""}</p>
        <form id="fxs-form" novalidate>
          <div class="fxs-field" data-f="parent_name"><label>Имя родителя</label>
            <input name="parent_name" autocomplete="name" placeholder="Как к вам обращаться">
            <div class="fxs-err">Укажите имя</div></div>
          <div class="fxs-field" data-f="phone"><label>Номер телефона родителя</label>
            <input name="phone" type="tel" autocomplete="tel" inputmode="tel" placeholder="+7 (___) ___-__-__">
            <div class="fxs-err">Укажите корректный номер</div></div>
          <div class="fxs-field" data-f="child_name"><label>Имя ребёнка</label>
            <input name="child_name" placeholder="Например, Маша"></div>
          <div class="fxs-field" data-f="child_age"><label>Возраст ребёнка</label>
            <input name="child_age" inputmode="numeric" placeholder="Например, 8"></div>
          <div class="fxs-actions">
            <button type="button" class="fxs-btn ghost" data-fxs="close">Отмена</button>
            <button type="submit" class="fxs-btn" ${state.sending ? "disabled" : ""}>${state.sending ? "Отправляем…" : "Записаться"}</button>
          </div>
        </form></div>`;
      ov.querySelector("#fxs-form").addEventListener("submit", onSubmit);
      const first = ov.querySelector("input");
      if (first) setTimeout(() => first.focus(), 50);
    }
    ov.addEventListener("click", (e) => { if (e.target === ov) closeModal(); });
    document.body.appendChild(ov);
  }

  function closeModal(rerender = true) {
    const old = document.getElementById("fxs-overlay");
    if (old) old.remove();
    if (rerender) state.bookingFor = null;
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
    if (!ok) return;

    state.sending = true; renderModal();
    const idem = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    const { status, body } = await api("/booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parent_name: val("parent_name"), phone: val("phone"),
        child_name: val("child_name"), child_age: val("child_age"),
        group_id: Number(state.bookingFor.groupId),
        lesson_id: Number(state.bookingFor.lessonId),
        source: "site-schedule", idempotency_key: idem,
      }),
    });
    state.sending = false;
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

  rootEl.addEventListener("click", (e) => {
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
    const t = e.target.closest('[data-fxs="filial"]');
    if (t) { state.filialId = t.value; track("filter_used", { filial_id: t.value }); load(); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.getElementById("fxs-overlay")) closeModal();
  });

  load();
})();
