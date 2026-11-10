"use client";

import { useEffect, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, LearningChallenge, LearningSession, LearningUnit } from "@/lib/api";

export default function LearnPage() {
  return <CabinetPage><Learning /></CabinetPage>;
}

function Learning() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active } = useCabinet();
  const [units, setUnits] = useState<LearningUnit[]>([]);
  const [session, setSession] = useState<LearningSession | null>(null);
  const [index, setIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token || !active) return;
    api.learningCatalog(token).then((r) => setUnits(r.units)).catch(() => setMessage(ru ? "Не удалось загрузить путь обучения." : "Could not load the learning path."));
  }, [token, active, ru]);

  async function start(unit: LearningUnit) {
    if (!token) return;
    setMessage("");
    setSession(await api.learningStart(token, studentId, unit.id));
    setIndex(0);
  }

  async function answer(answer: Record<string, unknown>) {
    if (!token || !session || busy) return;
    setBusy(true);
    try {
      const challenge = session.challenges[index];
      const result = await api.learningAnswer(token, studentId, session.session_id, challenge.id, answer);
      setMessage(result.correct ? (ru ? "Верно!" : "Correct!") : (ru ? "Попробуй ещё раз." : "Try again."));
      if (result.correct) {
        if (result.remaining === 0) await api.learningFinish(token, studentId, session.session_id);
        else setIndex((value) => value + 1);
      }
    } finally { setBusy(false); }
  }

  if (!session) return (
    <div className="k-page-grid">
      <div className="k-words-head"><div><h1>{ru ? "Путь обучения" : "Learning path"}</h1><p>{ru ? "Задания по словам, грамматике, чтению и аудированию." : "Vocabulary, grammar, reading and listening tasks."}</p></div></div>
      {message && <div className="k-alert">{message}</div>}
      <div className="k-set-grid">{units.map((unit) => <button className="k-set-card" key={unit.id} onClick={() => void start(unit)}><span className="k-set-icon">✦</span><b>{ru ? unit.title_ru : unit.title_en}</b><small>{unit.level.toUpperCase()} · {unit.skills.join(" · ")}</small><span className="k-link-strong">{ru ? "Начать урок →" : "Start lesson →"}</span></button>)}</div>
    </div>
  );

  const challenge: LearningChallenge = session.challenges[index];
  return <div className="k-page-grid"><div className="k-words-head"><div><a className="k-back" href="/learn">← {ru ? "Путь обучения" : "Learning path"}</a><h1>{ru ? session.unit.title_ru : session.unit.title_en}</h1><p>{index + 1} / {session.challenges.length}</p></div></div><section className="k-panel k-learning-task"><span className="k-task-kind">{challenge.kind.replaceAll("_", " ")}</span><h2>{challenge.prompt}</h2>{challenge.options.length > 0 && <div className="k-task-options">{challenge.options.map((option, i) => <button className="k-btn k-btn-light" key={option} disabled={busy} onClick={() => void answer({ index: i })}>{option}</button>)}</div>}{challenge.kind === "read_true_false" && <div className="k-task-options"><button className="k-btn k-btn-light" onClick={() => void answer({ value: true })}>True</button><button className="k-btn k-btn-light" onClick={() => void answer({ value: false })}>False</button></div>}{challenge.kind === "write" && <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); void answer({ text: String(form.get("text") || "") }); }}><input className="k-field-input" name="text" autoComplete="off" /><button className="k-btn k-btn-go" type="submit">{ru ? "Проверить" : "Check"}</button></form>}<p className="k-panel-note" aria-live="polite">{message}</p></section></div>;
}
