"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, Training, WordCard } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";
import { fmt, useI18n } from "@/lib/i18n";

type Task =
  | { kind: "choice"; card: WordCard; options: string[] }
  | { kind: "input"; card: WordCard };

type Result = { correct: number; wrong: number };

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function TrainPage() {
  const router = useRouter();
  const { t } = useI18n();
  const params = useParams<{ setId: string }>();
  const search = useSearchParams();
  const setId = Number(params.setId);
  const studentId = Number(search.get("student") || 0);

  const [training, setTraining] = useState<Training | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const token = getToken();
  const total = tasks.length;
  const task = tasks[idx];

  const speak = useCallback(
    (text: string) => {
      if (!token) return;
      void api
        .speak(token, text)
        .then((url) => {
          if (audioRef.current) {
            audioRef.current.pause();
            URL.revokeObjectURL(audioRef.current.src);
          }
          const a = new Audio(url);
          audioRef.current = a;
          void a.play().catch(() => {});
        })
        .catch(() => {});
    },
    [token],
  );

  const start = useCallback(async () => {
    if (!token || !setId) return;
    setError("");
    try {
      const out = await api.startTraining(token, studentId, setId);
      setTraining(out);
      const built: Task[] = [];
      for (const card of out.cards) {
        const answer = out.answers[card.id];
        // Задание «выбор перевода» — 3 дистрактора из набора.
        const options = shuffle([answer, ...card.distractors]).slice(0, 4);
        built.push({ kind: "choice", card, options });
        // Для слов, которые уже встречались (strength != null), добавляем ввод.
        if (card.strength != null) {
          built.push({ kind: "input", card });
        }
      }
      setTasks(shuffle(built));
      setIdx(0);
      setResult(null);
      setPicked(null);
      setInput("");
    } catch (err) {
      const status = (err as { status?: number }).status;
      if (status === 401) {
        clearSession();
        router.replace("/auth");
        return;
      }
      setError(t.train.startError);
    }
  }, [token, setId, studentId, router, t]);

  useEffect(() => {
    if (!token) {
      router.replace("/auth");
      return;
    }
    void start();
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }
    };
  }, [token, router, start]);

  // Озвучиваем английское слово автоматически при смене задания.
  useEffect(() => {
    if (task && training) {
      const card = task.card;
      if (card.audio_url) {
        const a = new Audio(card.audio_url);
        audioRef.current = a;
        void a.play().catch(() => {});
      } else {
        speak(card.text_en);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, training]);

  async function submit(correct: boolean, cardId: number) {
    if (!token || !result) return;
    setResult({ correct: result.correct + (correct ? 1 : 0), wrong: result.wrong + (correct ? 0 : 1) });
    try {
      await api.wordAnswer(token, studentId, cardId, correct);
    } catch { /* прогресс не записался — слово вернётся позже */ }
  }

  function onChoice(option: string) {
    if (!training || !task || task.kind !== "choice" || picked) return;
    const answer = training.answers[task.card.id];
    const ok = option === answer;
    setPicked(option);
    void submit(ok, task.card.id);
  }

  function next() {
    setPicked(null);
    setInput("");
    if (idx + 1 >= total) {
      setTraining((t) => (t ? { ...t, cards: [] } : t));
      return;
    }
    setIdx(idx + 1);
  }

  const finished = useMemo(
    () => training !== null && training.cards.length === 0,
    [training],
  );

  function onInputSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!training || !task || task.kind !== "input" || picked) return;
    const answer = training.answers[task.card.id];
    const ok = input.trim().toLowerCase() === answer.trim().toLowerCase();
    setPicked(ok ? "ok" : "no");
    void submit(ok, task.card.id);
  }

  if (error) {
    return (
      <main className="shell-main">
        <div className="alert alert-error">{error}</div>
        <a className="btn btn-ghost btn-sm" href="/words">{t.train.backToSets}</a>
      </main>
    );
  }

  if (!training || !task) {
    return (
      <main className="shell-main">
        <div className="card center-card">
          <p className="card-sub" style={{ marginBottom: 0 }}>
            {t.train.loading}
          </p>
        </div>
      </main>
    );
  }

  if (finished && result) {
    const all = result.correct + result.wrong;
    const pct = all ? ` · ${Math.round((result.correct / all) * 100)}%` : "";
    return (
      <main className="shell-main">
        <div className="card center-card">
          <h1 className="card-title">{t.train.doneTitle}</h1>
          <p className="card-sub">
            {fmt(t.train.doneSub, { correct: result.correct, all, pct })}
          </p>
          <div className="bot-links">
            <button className="btn btn-primary" onClick={() => void start()}>
              {t.train.again}
            </button>
            <a className="btn btn-ghost" href="/words">
              {t.train.toSets}
            </a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="shell-main">
      <div className="train-top">
        <a className="btn btn-ghost btn-sm" href="/words">{t.train.back}</a>
        <div className="train-progress">
          <div className="train-progress-fill" style={{ width: `${(idx / total) * 100}%` }} />
        </div>
        <span className="train-counter">
          {idx + 1} / {total}
        </span>
      </div>

      {task.kind === "choice" && (
        <section className="card train-card">
          {task.card.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="train-img" src={task.card.image_url} alt="" />
          ) : null}
          <button
            className="train-word"
            onClick={() => speak(task.card.text_en)}
            title={t.train.speakTitle}
          >
            {task.card.text_en}
            {task.card.transcription ? (
              <span className="train-tr">{task.card.transcription}</span>
            ) : null}
            <span className="train-speak">🔊</span>
          </button>
          <div className="train-options">
            {task.options.map((opt) => {
              const answer = training.answers[task.card.id];
              let cls = "";
              if (picked) {
                if (opt === answer) cls = " opt-correct";
                else if (opt === picked) cls = " opt-wrong";
              }
              return (
                <button
                  key={opt}
                  className={"train-opt" + cls}
                  disabled={!!picked}
                  onClick={() => onChoice(opt)}
                >
                  {opt}
                </button>
              );
            })}
          </div>
          {picked && (
            <button className="btn btn-primary" onClick={next}>
              {idx + 1 >= total ? t.train.finish : t.train.next}
            </button>
          )}
        </section>
      )}

      {task.kind === "input" && (
        <section className="card train-card">
          <p className="train-prompt">{t.train.promptInput}</p>
          <div className="train-ru">{training.answers[task.card.id]}</div>
          <form className="train-input-row" onSubmit={onInputSubmit}>
            <input
              className="train-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="english word"
              autoComplete="off"
              autoFocus
              disabled={!!picked}
            />
            {!picked ? (
              <button className="btn btn-primary btn-sm" type="submit">
                {t.train.check}
              </button>
            ) : (
              <button
                className="btn btn-primary btn-sm"
                type="button"
                onClick={next}
              >
                {idx + 1 >= total ? t.train.finish : t.train.next}
              </button>
            )}
          </form>
          {picked && (
            <p className={"train-feedback " + (picked === "ok" ? "fb-ok" : "fb-bad")}>
              {picked === "ok"
                ? t.train.correct
                : `${t.train.wrong} ${task.card.text_en} (${training.answers[task.card.id]})`}
            </p>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => speak(task.card.text_en)}>
            {t.train.listen}
          </button>
        </section>
      )}
    </main>
  );
}
