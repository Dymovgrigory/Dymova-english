"use client";

import { useEffect, useMemo, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, WordSet } from "@/lib/api";
import { topicLook } from "@/lib/topics";
import { ArrowRight, BookOpenText, ListChecks } from "lucide-react";

export default function WordsPage() {
  return (
    <CabinetPage>
      <Library />
    </CabinetPage>
  );
}

type Tab = "start" | "topics" | "levels" | "school";

function Library() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active, stats } = useCabinet();
  const [sets, setSets] = useState<WordSet[] | null>(null);
  const [tab, setTab] = useState<Tab>("start");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !active) return;
    api.wordSets(token, studentId)
      .then((r) => setSets(r.sets))
      .catch(() => setError(ru ? "Не удалось загрузить словари. Обновите страницу." : "Could not load word lists. Refresh the page."));
  }, [token, active, studentId, ru]);

  const groups = useMemo(() => {
    const all = sets ?? [];
    const topics = all.filter((s) => s.kind === "topic");
    const levels = all.filter((s) => s.kind === "level");
    const school = all.filter((s) => s.kind === "book" || (!s.is_public && s.kind !== "topic"));
    const due = all.filter((s) => s.progress.due > 0).sort((a, b) => b.progress.due - a.progress.due);
    const started = all.filter((s) => s.progress.seen > 0 && s.progress.learned < s.progress.total && s.progress.due === 0);
    const firsts = topics.filter((s) => /:1$/.test(s.code) || !/:\d+$/.test(s.code)).slice(0, 8);
    return { topics, levels, school, due, started, firsts };
  }, [sets]);

  const filtered = (list: WordSet[]) =>
    q.trim() ? list.filter((s) => s.title.toLowerCase().includes(q.trim().toLowerCase())) : list;

  const totalDue = groups.due.reduce((n, s) => n + s.progress.due, 0);

  return (
    <div className="k-words">
      <section className="k-words-head">
        <div>
          <h1>{ru ? "Тренажёр слов" : "Word trainer"}</h1>
          <p>{ru
            ? `${sets ? sets.reduce((n, s) => n + (s.kind === "level" ? 0 : s.progress.total), 0) : "…"} слов с картинками, озвучкой и транскрипцией. Учи по темам или по уровням.`
            : "Words with pictures, audio and IPA. Learn by topic or by level."}</p>
        </div>
        <div className="k-words-stats">
          <div><b>{stats?.learned_words ?? 0}</b><span>{ru ? "выучено" : "learned"}</span></div>
          <div><b>{stats?.due_today ?? totalDue}</b><span>{ru ? "повторить" : "to review"}</span></div>
          <div><b>{stats && stats.answers_total ? Math.round((stats.answers_correct / stats.answers_total) * 100) : 0}%</b><span>{ru ? "точность" : "accuracy"}</span></div>
        </div>
      </section>

      {error && <div className="k-alert">{error}</div>}

      <div className="k-tabs" role="tablist">
        {([
          ["start", ru ? "С чего начать" : "Start here"],
          ["topics", ru ? "Темы" : "Topics"],
          ["levels", ru ? "Уровни" : "Levels"],
          ["school", ru ? "Учебники" : "Textbooks"],
        ] as [Tab, string][]).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={"k-tab-btn" + (tab === k ? " is-on" : "")} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
        {tab === "topics" && (
          <label className="k-search">
            <span className="sr-only">{ru ? "Найти тему" : "Find a topic"}</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ru ? "Найти тему" : "Find a topic"} />
          </label>
        )}
      </div>

      {!sets && !error && <div className="k-skeleton-grid">{Array.from({ length: 8 }, (_, i) => <div key={i} className="k-skel" />)}</div>}

      {sets && tab === "start" && (
        <>
          {groups.due.length > 0 && (
            <SetBlock title={ru ? `Пора повторить · ${totalDue}` : `Time to review · ${totalDue}`} sets={groups.due.slice(0, 4)} ru={ru} />
          )}
          {groups.started.length > 0 && <SetBlock title={ru ? "Продолжить" : "Continue"} sets={groups.started.slice(0, 4)} ru={ru} />}
          <SetBlock title={ru ? "Для самых маленьких" : "For little ones"} sets={groups.levels.filter((s) => s.code === "level:pre-a1")} ru={ru} wide />
          <SetBlock title={ru ? "Популярные темы" : "Popular topics"} sets={groups.firsts} ru={ru} />
        </>
      )}
      {sets && tab === "topics" && <SetBlock title="" sets={filtered(groups.topics)} ru={ru} />}
      {sets && tab === "levels" && <SetBlock title="" sets={groups.levels} ru={ru} wide />}
      {sets && tab === "school" && (
        groups.school.length
          ? <SetBlock title="" sets={groups.school} ru={ru} />
          : <div className="k-empty">
              <BookOpenText size={56} strokeWidth={1.6} />
              <p>{ru ? "Здесь появятся слова к учебникам вашей группы (My Level, Get Involved, Spotlight), когда педагог их откроет." : "Textbook word lists appear here once your teacher assigns them."}</p>
            </div>
      )}

      <p className="k-credits">
        {ru ? "Картинки: школа Фоксинбург (созданы в Meshy). Уровни слов: CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS). Транскрипция: ipa-dict." : "Pictures: Foxinburg school (made with Meshy). Word levels: CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS). IPA: ipa-dict."}
      </p>
    </div>
  );
}

function SetBlock({ title, sets, ru, wide = false }: { title: string; sets: WordSet[]; ru: boolean; wide?: boolean }) {
  if (!sets.length) return null;
  return (
    <section className="k-setblock">
      {title && <h2>{title}</h2>}
      <div className={"k-sets" + (wide ? " is-wide" : "")}>
        {sets.map((s) => <SetCard key={s.id} s={s} ru={ru} />)}
      </div>
    </section>
  );
}

function SetCard({ s, ru }: { s: WordSet; ru: boolean }) {
  const p = s.progress;
  const pct = p.total ? Math.round((p.learned / p.total) * 100) : 0;
  const done = p.total > 0 && p.learned >= p.total;
  const look = topicLook(s.code, s.topic);
  const pics = (s.preview ?? []).filter((x) => !x.startsWith("/wimg/")).slice(0, 3);
  const Icon = look.Icon;
  return (
    <article className="k-set" style={{ ["--c" as string]: look.color, ["--ci" as string]: look.ink }}>
      <a className="k-set-main" href={`/words/train/${s.id}`}>
        <div className={"k-set-cover" + (pics.length ? " has-pics" : "")} aria-hidden="true">
          <span className="k-set-icon"><Icon size={22} strokeWidth={2.4} /></span>
          {pics.length > 0
            ? <div className="k-set-photos">{pics.map((src, i) => <img key={i} src={src} alt="" width={96} height={96} loading="lazy" />)}</div>
            : <Icon className="k-set-bigicon" size={84} strokeWidth={1.6} />}
        </div>
        <div className="k-set-body">
          <h3>{s.title}</h3>
          <p>{ru ? `${p.total} слов` : `${p.total} words`}{p.due > 0 ? (ru ? ` · повторить ${p.due}` : ` · review ${p.due}`) : ""}{p.learned > 0 ? (ru ? ` · выучено ${pct}%` : ` · ${pct}% learned`) : ""}</p>
          <div className="k-bar"><i style={{ width: `${pct}%` }} /></div>
          <span className="k-set-go">{done ? (ru ? "Повторить" : "Review") : p.seen ? (ru ? "Продолжить" : "Continue") : (ru ? "Начать" : "Start")}<ArrowRight size={16} strokeWidth={3} /></span>
        </div>
      </a>
      <a className="k-set-list" href={`/words/set/${s.id}`}><ListChecks size={16} strokeWidth={2.4} />{ru ? "Все слова и режимы" : "All words and modes"}</a>
    </article>
  );
}
