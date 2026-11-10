"use client";

// Главная кабинета. Награды — своя система «Фоксинбурга» (не очки и «огонёк»):
// монеты Мира, звание жителя, календарь Фокси, сундук недели, задание дня,
// коллекция открыток тем, карточек героев и медали уровней Cambridge.
import { useEffect, useMemo, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, GameStats, Lesson, WordSet } from "@/lib/api";
import { celebrate } from "@/lib/fx";
import { sfx } from "@/lib/sound";
import { Castle, Coins, Gift, Lock, Medal, PawPrint, Scroll, Shield, Target } from "lucide-react";

export default function DashboardPage() {
  return (
    <CabinetPage>
      <Dashboard />
    </CabinetPage>
  );
}

const DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const DAYS_EN = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
const MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];

function ymd(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function Dashboard() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, me, active, studentId, stats, refreshStats } = useCabinet();
  const [sets, setSets] = useState<WordSet[]>([]);
  const [lesson, setLesson] = useState<Lesson | null | undefined>(undefined);
  const [hard, setHard] = useState(0);
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    if (!token || !active) return;
    api.wordSets(token, studentId).then((r) => setSets(r.sets)).catch(() => setSets([]));
    api.myWords(token, studentId).then((r) => setHard(r.hard_ids.length)).catch(() => setHard(0));
    if (active.student_id) {
      const now = new Date();
      const to = new Date(now.getTime() + 14 * 86400000);
      api.schedule(token, active.student_id, ymd(now), ymd(to))
        .then((s) => {
          const next = s.lessons
            .filter((l) => new Date(l.starts_at || l.date).getTime() >= now.getTime() - 3600000)
            .sort((a, b) => (a.starts_at || a.date).localeCompare(b.starts_at || b.date))[0];
          setLesson(next ?? null);
        })
        .catch(() => setLesson(null));
    } else {
      setLesson(null);
    }
  }, [token, active, studentId]);

  const continueSet = useMemo(() => {
    const due = [...sets].sort((a, b) => b.progress.due - a.progress.due)[0];
    if (due && due.progress.due > 0) return due;
    const started = sets.find((s) => s.progress.seen > 0 && s.progress.seen < s.progress.total);
    return started ?? sets.find((s) => s.code === "level:pre-a1") ?? sets[0];
  }, [sets]);

  async function claim(kind: "quest" | "chest") {
    if (!token || busy) return;
    setBusy(kind);
    try {
      const r = await api.wordClaim(token, studentId, kind);
      sfx("level");
      celebrate(true);
      setToast(ru ? `+${r.coins} монет! Они уже в кошельке Мира.` : `+${r.coins} coins! They're in your World wallet.`);
      setTimeout(() => setToast(""), 3500);
      await refreshStats();
    } catch {
      setToast(ru ? "Не получилось забрать награду. Попробуйте ещё раз." : "Could not claim the reward. Try again.");
    } finally {
      setBusy("");
    }
  }

  const s = stats as Partial<GameStats> | null;
  const name = active?.child_name || me?.account.parent_name || "";
  const rank = s?.rank;
  const rankPct = rank ? Math.round(((rank.learned - rank.from) / Math.max(1, rank.to - rank.from)) * 100) : 0;
  const quest = s?.quest;
  const week = s?.week;
  const month = s?.month;
  const firstWeekday = month ? (new Date(month.year, month.month - 1, 1).getDay() + 6) % 7 : 0;
  const today = ymd(new Date());

  return (
    <div className="k-dash">
      <section className="k-hero">
        <div className="k-hero-text">
          <h1>{ru ? `Привет, ${name}!` : `Hi, ${name}!`}</h1>
          <p>
            {quest && !quest.done
              ? ru ? `Задание дня от Фокси: ${quest.title.toLowerCase()}.` : `Foxi's task for today: ${quest.title}.`
              : ru ? "Задание дня выполнено. Можно учить дальше или заглянуть в Мир." : "Today's task is done. Keep learning or visit the World."}
          </p>
          {continueSet && (
            <a className="k-btn k-btn-go k-btn-lg" href={`/words/train/${continueSet.id}`}>
              {continueSet.progress.due > 0
                ? ru ? `Повторить слова · ${continueSet.progress.due}` : `Review words · ${continueSet.progress.due}`
                : ru ? "Учить новые слова" : "Learn new words"}
            </a>
          )}
          {continueSet && <div className="k-hero-set">{continueSet.title}</div>}
        </div>
        <a className="k-hero-foxlink" href="/foxi" title={ru ? "Создай своего Фокси" : "Make your own Foxi"}>
          <img className="k-hero-fox" src="/foxi/guide.webp" alt={ru ? "Фокси" : "Foxi"} width={260} height={428} />
          <span className="k-hero-foxcta">{ru ? "Создай своего Фокси" : "Make your Foxi"}</span>
        </a>
      </section>

      {toast && <div className="k-toast" role="status">{toast}</div>}

      <div className="k-dash-grid">
        <section className="k-panel g-quest">
          <h2><Scroll size={22} strokeWidth={2.4} />{ru ? "Задание дня" : "Task of the day"}</h2>
          {quest ? (
            <>
              <p className="g-quest-title">{quest.title}</p>
              <div className="k-bar g-bar"><i style={{ width: `${Math.round((quest.progress / quest.target) * 100)}%` }} /></div>
              <p className="k-panel-note">{quest.progress} / {quest.target}</p>
              {quest.claimed ? (
                <p className="g-done">{ru ? `Награда получена: +${quest.reward}` : `Reward claimed: +${quest.reward}`}</p>
              ) : (
                <button className="k-btn k-btn-go" disabled={!quest.done || !!busy} onClick={() => void claim("quest")}>
                  <Coins size={18} strokeWidth={2.6} />{ru ? `Забрать ${quest.reward} монет` : `Claim ${quest.reward} coins`}
                </button>
              )}
            </>
          ) : <p className="k-panel-note">…</p>}
        </section>

        <section className="k-panel g-chest">
          <h2><Gift size={22} strokeWidth={2.4} />{ru ? "Сундук недели" : "Weekly chest"}</h2>
          <div className="g-week">
            {(week?.days ?? []).map((d, i) => (
              <span key={d.day} className={"g-week-day" + (d.active ? " is-on" : "") + (d.day === today ? " is-today" : "")}>
                {d.active ? <PawPrint size={18} strokeWidth={2.6} /> : null}
                <em>{(ru ? DAYS_RU : DAYS_EN)[i]}</em>
              </span>
            ))}
          </div>
          <p className="k-panel-note">
            {ru ? `${week?.active_days ?? 0} из ${week?.need ?? 5} дней на этой неделе` : `${week?.active_days ?? 0} of ${week?.need ?? 5} days this week`}
          </p>
          {week?.chest_claimed ? (
            <p className="g-done">{ru ? "Сундук открыт. Новый — в понедельник." : "Chest opened. A new one on Monday."}</p>
          ) : (
            <button className="k-btn k-btn-go" disabled={!week?.chest_ready || !!busy} onClick={() => void claim("chest")}>
              {week?.chest_ready ? <Gift size={18} strokeWidth={2.6} /> : <Lock size={18} strokeWidth={2.6} />}
              {ru ? `Открыть: ${week?.reward ?? 30} монет` : `Open: ${week?.reward ?? 30} coins`}
            </button>
          )}
        </section>

        <section className="k-panel g-rank">
          <h2><Shield size={22} strokeWidth={2.4} />{ru ? "Звание" : "Rank"}</h2>
          <div className="g-rank-badge"><span>{rank?.index ?? 1}</span><b>{rank?.title ?? "…"}</b></div>
          <div className="k-bar g-bar"><i style={{ width: `${Math.max(3, Math.min(100, rankPct))}%` }} /></div>
          <p className="k-panel-note">
            {rank?.next_title
              ? ru ? `Выучено ${rank.learned} слов. До звания «${rank.next_title}» — ${rank.to - rank.learned}.` : `${rank.learned} words learned. ${rank.to - rank.learned} more to “${rank.next_title}”.`
              : ru ? "Высшее звание Фоксинбурга!" : "The highest rank in Foxinburg!"}
          </p>
        </section>

        <section className="k-panel g-wallet">
          <h2><Coins size={22} strokeWidth={2.4} />{ru ? "Монеты Фоксинбурга" : "Foxinburg coins"}</h2>
          <div className="g-coins"><b>{s?.wallet ?? 0}</b><span>{ru ? `+${s?.coins_today ?? 0} сегодня` : `+${s?.coins_today ?? 0} today`}</span></div>
          <p className="k-panel-note">{ru ? "Трать в магазине Мира: башни, украшения и наряды для замка." : "Spend them in the World shop: towers, decor and outfits."}</p>
          <a className="k-btn k-btn-light" href="/world"><Castle size={18} strokeWidth={2.4} />{ru ? "В магазин Мира" : "To the World shop"}</a>
        </section>

        <section className="k-panel k-lesson">
          <h2>{ru ? "Следующий урок" : "Next lesson"}</h2>
          {lesson === undefined && <p className="k-panel-note">…</p>}
          {lesson === null && (
            <p className="k-panel-text">
              {active?.student_id
                ? ru ? "На ближайшие две недели уроков нет." : "No lessons in the next two weeks."
                : ru ? "Расписание появится, когда ребёнок начнёт заниматься в школе." : "The schedule appears once your child joins a group."}
            </p>
          )}
          {lesson && (
            <>
              <p className="k-lesson-when">
                {new Date(lesson.starts_at || lesson.date).toLocaleDateString(ru ? "ru-RU" : "en-GB", { weekday: "long", day: "numeric", month: "long" })}
                {lesson.starts_at && <>, {new Date(lesson.starts_at).toLocaleTimeString(ru ? "ru-RU" : "en-GB", { hour: "2-digit", minute: "2-digit" })}</>}
              </p>
              <p className="k-panel-text">{lesson.group.caption}{lesson.filial.caption ? ` · ${lesson.filial.caption}` : ""}</p>
            </>
          )}
          <a className="k-link-strong" href="/schedule">{ru ? "Всё расписание" : "Full schedule"}</a>
        </section>

        <section className="k-panel g-hard">
          <h2><Target size={22} strokeWidth={2.4} />{ru ? "Трудные слова" : "Tricky words"}</h2>
          <div className="g-coins"><b>{hard}</b><span>{ru ? "слов с ошибками" : "words with mistakes"}</span></div>
          <p className="k-panel-note">{ru ? "Слова, в которых были ошибки, собираются в отдельный урок." : "Words you got wrong are gathered into a special lesson."}</p>
          {hard > 0
            ? <a className="k-btn k-btn-go" href="/words/train/0">{ru ? "Потренировать" : "Practise them"}</a>
            : <a className="k-btn k-btn-light" href="/words/my">{ru ? "Мой словарь" : "My words"}</a>}
        </section>
      </div>

      <section className="k-panel g-cal">
        <h2><PawPrint size={22} strokeWidth={2.4} />{ru ? `Календарь Фокси · ${month ? MONTHS_RU[month.month - 1] : ""}` : "Foxi's calendar"}</h2>
        <p className="k-panel-note">
          {ru ? `Лапка за каждый день занятий. В этом месяце: ${month?.active_days ?? 0}. Пропуск ничего не сгорает — просто возвращайся.`
            : `A paw print for every day you practise. This month: ${month?.active_days ?? 0}.`}
        </p>
        <div className="g-cal-grid">
          {(ru ? DAYS_RU : DAYS_EN).map((d) => <span key={d} className="g-cal-head">{d}</span>)}
          {Array.from({ length: firstWeekday }).map((_, i) => <span key={"e" + i} />)}
          {(month?.days ?? []).map((d) => (
            <span key={d.day} className={"g-cal-day" + (d.active ? " is-on" : "") + (d.day === today ? " is-today" : "")}
              title={d.active ? (ru ? `+${d.coins} монет` : `+${d.coins} coins`) : ""}>
              {d.active ? <PawPrint size={20} strokeWidth={2.6} /> : <em>{Number(d.day.slice(8))}</em>}
            </span>
          ))}
        </div>
      </section>

      <section className="k-panel g-collection">
        <h2><Scroll size={22} strokeWidth={2.4} />{ru ? `Коллекция открыток · ${s?.postcards_unlocked ?? 0} из ${s?.postcards?.length ?? 0}` : `Postcards · ${s?.postcards_unlocked ?? 0} of ${s?.postcards?.length ?? 0}`}</h2>
        <p className="k-panel-note">{ru ? "Открытка темы открывается, когда выучено 80% её слов." : "A topic postcard opens when you know 80% of its words."}</p>
        <div className="g-cards">
          {(s?.postcards ?? []).map((c) => (
            <a key={c.topic} className={"g-card" + (c.unlocked ? " is-open" : "")} href={`/words/set/${c.set_id}`}>
              <span className="g-card-img">{c.cover ? <img src={c.cover} alt="" width={160} height={160} loading="lazy" /> : null}
                {!c.unlocked && <i className="g-card-lock"><Lock size={18} strokeWidth={2.6} /></i>}</span>
              <b>{c.title}</b>
              <span className="g-card-bar"><i style={{ width: `${c.percent}%` }} /></span>
              <em>{c.percent}%</em>
            </a>
          ))}
        </div>
      </section>

      <section className="k-panel g-medals">
        <h2><Medal size={22} strokeWidth={2.4} />{ru ? "Медали уровней" : "Level medals"}</h2>
        <p className="k-panel-note">{ru ? "Уровни как на экзаменах Cambridge для детей. Медаль — за 80% слов уровня." : "Levels as in Cambridge exams for young learners. A medal for 80% of the words."}</p>
        <div className="g-medal-row">
          {(s?.medals ?? []).map((m) => (
            <a key={m.code} className={"g-medal" + (m.earned ? " is-on" : "")} href={`/words/set/${m.set_id}`}>
              <span className="g-medal-disc"><Medal size={34} strokeWidth={2.2} /></span>
              <b>{m.name}</b><em>{m.cefr} · {m.learned} / {m.total}</em>
              <span className="g-card-bar"><i style={{ width: `${m.percent}%` }} /></span>
            </a>
          ))}
        </div>
      </section>

      <section className="k-panel g-collection">
        <h2><Gift size={22} strokeWidth={2.4} />{ru ? `Коллекция героев · ${s?.collection_cards?.length ?? 0} из ${s?.collection_total ?? 0}` : `Character collection · ${s?.collection_cards?.length ?? 0} of ${s?.collection_total ?? 0}`}</h2>
        <p className="k-panel-note">{ru ? "Карточки открываются за реальные учебные достижения." : "Cards unlock for real learning achievements."}</p>
        <div className="g-medal-row">
          {(s?.achievements ?? []).map((a) => (
            <div key={a.id} className={"g-medal" + (a.unlocked ? " is-on" : "")}>
              <span className="g-medal-disc"><Gift size={30} strokeWidth={2.2} /></span>
              <b>{a.title}</b><em>{a.unlocked ? (ru ? "Открыто" : "Unlocked") : (ru ? "Ещё впереди" : "Keep learning")}</em>
            </div>
          ))}
        </div>
      </section>

      <a className="k-world-banner" href="/world">
        <div>
          <h2>{ru ? "Мир Фоксинбурга" : "Foxinburg World"}</h2>
          <p>{ru ? "Строй свой замок на монеты, заработанные за слова." : "Build your castle with the coins you earn for words."}</p>
        </div>
        <span className="k-btn k-btn-light"><Castle size={20} strokeWidth={2.4} />{ru ? "Войти в Мир" : "Enter the World"}</span>
      </a>
    </div>
  );
}
