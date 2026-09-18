"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/design/Button";
import { FeedbackSheet } from "@/design/FeedbackSheet";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { ProgressBar } from "@/design/ProgressBar";
import { ApiError } from "@/lib/api";
import { playCorrect, playWrong } from "@/lib/sfx";
import { speakEnglish } from "@/lib/speak";
import { isProfileMissing, v2 } from "@/lib/v2/client";
import { currentChallenge, initLesson, lessonReducer, progressOf } from "@/lib/v2/lessonState";
import { pauseSpeaking, speakAllowed } from "@/lib/v2/media";
import { speechRecognitionSupported } from "@/lib/v2/speech";
import type { Answer, Challenge, SessionResult, SessionStart } from "@/lib/v2/types";

import {
  ChoiceChallenge,
  PairsChallenge,
  TeachGrapheme,
  TeachRule,
  TeachWord,
  TilesChallenge,
  TypeChallenge,
  type ViewProps,
} from "./challengeViews";
import { FinishScreen } from "./FinishScreen";
import { SpeakChallenge } from "./SpeakChallenge";

const TILE_TYPES = new Set<Challenge["type"]>(["spell_tiles", "build_phrase", "listen_build"]);

/** Испытание дня: 15 секунд на вопрос, с небольшим запасом, чтобы response_ms уложился в правило сервера. */
const TRIAL_SECONDS = 15;
const TRIAL_TIMEOUT_MS = TRIAL_SECONDS * 1000 - 200;

function ChallengeView(props: ViewProps & { onSkip: () => void; onHeard: (t: string) => void }) {
  const { challenge } = props;
  switch (challenge.type) {
    case "teach_word":
      return <TeachWord challenge={challenge} />;
    case "teach_rule":
      return <TeachRule challenge={challenge} />;
    case "teach_grapheme":
      return <TeachGrapheme challenge={challenge} />;
    case "match_pairs":
      return <PairsChallenge {...props} />;
    case "type_word":
      return <TypeChallenge {...props} />;
    case "speak":
      return <SpeakChallenge {...props} />;
    default:
      return TILE_TYPES.has(challenge.type) ? <TilesChallenge {...props} /> : <ChoiceChallenge {...props} />;
  }
}

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; session: SessionStart };

async function requestSession(nodeId: string): Promise<LoadState | "onboarding"> {
  try {
    const allowSpeak = speakAllowed() && speechRecognitionSupported();
    const session =
      nodeId === "practice"
        ? await v2.startPractice(allowSpeak)
        : nodeId === "trial"
          ? await v2.startPractice(allowSpeak, "trial")
          : await v2.startSession(nodeId, allowSpeak);
    return { status: "ready", session };
  } catch (err) {
    if (isProfileMissing(err)) return "onboarding";
    const message =
      err instanceof ApiError && err.message === "node_locked"
        ? "Этот урок пока закрыт. Сначала пройди предыдущие."
        : err instanceof ApiError && err.message === "nothing_to_practice"
          ? "Пока нечего повторять. Пройди пару уроков — и слабые слова появятся здесь."
          : err instanceof ApiError && err.message === "trial_not_available"
            ? "Испытание пока недоступно. Сначала выучи слова на уроках."
            : err instanceof Error
              ? err.message
              : "Не получилось открыть урок.";
    return { status: "error", message };
  }
}

export function LessonScreen({ nodeId }: { nodeId: string }) {
  const router = useRouter();
  const isTrial = nodeId === "trial";
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [result, setResult] = useState<SessionResult | null>(null);
  const [confirmExit, setConfirmExit] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [lessonState, setLessonState] = useState(() => initLesson([]));
  const [trialLeft, setTrialLeft] = useState(TRIAL_SECONDS);
  const shownAt = useRef(0);

  const applyLoad = useCallback(
    (next: LoadState | "onboarding") => {
      if (next === "onboarding") {
        router.replace("/onboarding");
        return;
      }
      if (next.status === "ready") {
        setLessonState(initLesson(next.session.challenges));
        setAttempt(0);
      }
      setLoad(next);
    },
    [router],
  );

  useEffect(() => {
    let alive = true;
    requestSession(nodeId).then((next) => {
      if (alive) applyLoad(next);
    });
    return () => {
      alive = false;
    };
  }, [applyLoad, nodeId]);

  const restart = useCallback(() => {
    setLoad({ status: "loading" });
    setResult(null);
    void requestSession(nodeId).then(applyLoad);
  }, [applyLoad, nodeId]);

  const session = load.status === "ready" ? load.session : null;
  const act = useCallback((action: Parameters<typeof lessonReducer>[1]) => {
    setLessonState((prev) => lessonReducer(prev, action));
  }, []);

  const challenge = currentChallenge(lessonState);

  useEffect(() => {
    shownAt.current = Date.now();
  }, [challenge, attempt]);

  const submit = useCallback(
    async (answer: Answer) => {
      if (!session || !challenge) return;
      act({ type: "checking" });
      try {
        const reply = await v2.answer(session.session_id, challenge.index, answer, Date.now() - shownAt.current);
        if (!challenge.graded) {
          act({ type: "answered", reply });
          act({ type: "continue" });
          setAttempt((n) => n + 1);
          return;
        }
        if (!reply.skipped) (reply.correct ? playCorrect : playWrong)();
        if (challenge.reveal_audio) void speakEnglish(challenge.reveal_audio);
        act({ type: "answered", reply });
      } catch (err) {
        act({ type: "failed", message: err instanceof Error ? err.message : "Нет связи. Попробуй ещё раз." });
      }
    },
    [act, challenge, session],
  );

  const next = useCallback(() => {
    act({ type: "continue" });
    setAttempt((n) => n + 1);
  }, [act]);

  // Испытание дня: 15 с на вопрос, по таймауту — заведомо неверный ответ, дальше обычная логика урока.
  useEffect(() => {
    if (!isTrial || !challenge?.graded || lessonState.phase !== "answering") return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- запуск отсчёта для нового вопроса
    setTrialLeft(TRIAL_SECONDS);
    const started = Date.now();
    const tick = window.setInterval(() => {
      setTrialLeft(Math.max(0, Math.ceil(TRIAL_SECONDS - (Date.now() - started) / 1000)));
    }, 200);
    const timeout = window.setTimeout(() => void submit({}), TRIAL_TIMEOUT_MS);
    return () => {
      window.clearInterval(tick);
      window.clearTimeout(timeout);
    };
  }, [isTrial, challenge, attempt, lessonState.phase, submit]);

  // Финиш, когда очередь опустела.
  useEffect(() => {
    if (!session || lessonState.phase !== "done" || result || !session.challenges.length) return;
    v2.finish(session.session_id)
      .then(setResult)
      .catch((err) => act({ type: "failed", message: err instanceof Error ? err.message : "Не получилось сохранить урок." }));
  }, [act, lessonState.phase, result, session]);

  // Клавиатура: 1–4 выбирают вариант, Enter — проверить или дальше.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!challenge || confirmExit) return;
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT";
      if (event.key === "Enter") {
        if (lessonState.phase === "feedback") {
          event.preventDefault();
          next();
        } else if (lessonState.phase === "answering" && (lessonState.draft || !challenge.graded)) {
          event.preventDefault();
          void submit(lessonState.draft ?? {});
        }
        return;
      }
      const digit = Number(event.key);
      if (!typing && lessonState.phase === "answering" && digit >= 1 && digit <= (challenge.options?.length ?? 0)) {
        act({ type: "draft", answer: { index: digit - 1 } });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [act, challenge, confirmExit, lessonState.draft, lessonState.phase, next, submit]);

  if (result) {
    return (
      <FinishScreen
        result={result}
        onContinue={() => router.push("/learn")}
        onRetry={restart}
      />
    );
  }

  if (load.status !== "ready" || !challenge) {
    return (
      <div className="study flex min-h-dvh flex-col items-center justify-center gap-6 px-6 text-center">
        {load.status === "error" ? (
          <>
            <Foxy pose="think" size={150} />
            <p className="max-w-sm text-[20px] font-extrabold text-[#f6efe2]">{load.message}</p>
            <div className="flex gap-3">
              <Button variant="paper" onClick={() => router.push("/learn")}>К пути</Button>
              <Button onClick={restart}>Попробовать снова</Button>
            </div>
          </>
        ) : (
          <p className="text-[18px] font-extrabold text-[#c9bfd8]" role="status">
            {lessonState.phase === "done" && session ? "Сохраняем результат…" : "Готовим урок…"}
          </p>
        )}
        {lessonState.error && <p className="text-[16px] font-bold text-coral-ink">{lessonState.error}</p>}
      </div>
    );
  }

  const locked = lessonState.phase !== "answering";
  const footer = (
    <div className="flex flex-col gap-2">
      {lessonState.error && <p className="text-center text-[15px] font-bold text-coral-ink" role="alert">{lessonState.error}</p>}
      {challenge.type === "speak" || challenge.type === "match_pairs" ? (
        <p className="text-center text-[15px] font-bold text-[#c9bfd8]">
          {challenge.type === "speak" ? "Нажми на микрофон и прочитай фразу вслух" : "Соедини все пары — верные закрепятся сразу"}
        </p>
      ) : (
        <Button
          block
          disabled={(challenge.graded && !lessonState.draft) || lessonState.phase === "checking"}
          onClick={() => void submit(lessonState.draft ?? {})}
        >
          {challenge.graded ? "Проверить" : "Дальше"}
        </Button>
      )}
    </div>
  );

  const sceneModule = nodeId.split(".").slice(0, 2).join("-");
  return (
    <div className="study relative flex min-h-dvh flex-col">
      {nodeId !== "practice" && nodeId !== "trial" && (
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-0 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element -- размытая диорама этажа как атмосфера урока */}
          <img src={`/content/modules/${sceneModule}.webp`} alt="" className="h-full w-full scale-110 object-cover opacity-80 blur-[10px]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgb(21_15_31/0.25)_0%,rgb(21_15_31/0.8)_75%)]" />
        </div>
      )}
      <header className="relative z-10 mx-auto flex w-full max-w-2xl items-center gap-4 px-4 pt-5">
        <button
          type="button"
          aria-label="Выйти из урока"
          onClick={() => setConfirmExit(true)}
          className="flex size-11 items-center justify-center rounded-full text-[#f6efe2] hover:bg-white/10 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/60"
        >
          <Icon name="close" size={28} />
        </button>
        <ProgressBar value={progressOf(lessonState)} label="Прогресс урока" />
      </header>

      {isTrial && lessonState.phase === "answering" && challenge.graded ? (
        <div className="relative z-10 mx-auto mt-3 w-full max-w-2xl px-4" role="timer" aria-label={`Осталось ${trialLeft} секунд`}>
          <div className="flex items-center gap-3">
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-white/15">
              <div
                className={`h-full rounded-full transition-[width] duration-200 ${trialLeft <= 5 ? "bg-[#ff8a3d]" : "bg-[#ffd36e]"}`}
                style={{ width: `${(trialLeft / TRIAL_SECONDS) * 100}%` }}
              />
            </div>
            <span className="w-10 text-right text-[15px] font-extrabold tabular-nums text-[#f6efe2]">{trialLeft} с</span>
          </div>
        </div>
      ) : null}

      <main className="relative z-10 mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 pb-8 pt-6">
        <div className="mat-parchment rounded-[28px] px-5 py-6 sm:px-8 sm:py-8">
        <ChallengeView
          key={`${challenge.index}-${attempt}`}
          challenge={challenge}
          draft={lessonState.draft}
          locked={locked}
          reveal={lessonState.phase === "feedback" ? lessonState.feedback : null}
          onDraft={(answer) => act({ type: "draft", answer })}
          onSkip={() => {
            pauseSpeaking();
            void submit({ skip: true });
          }}
          onHeard={(transcript) => void submit({ transcript })}
          onCheckPair={async (left, right) => {
            try {
              if (!session) return false;
              return (await v2.checkPair(session.session_id, challenge.index, left, right)).correct;
            } catch {
              return false;
            }
          }}
          onSubmit={(answer) => void submit(answer)}
        />
        </div>
      </main>

      <div className="sticky bottom-0 z-20 lg:bottom-10 lg:px-4"><FeedbackSheet reply={lessonState.phase === "feedback" ? lessonState.feedback : null} onContinue={next} footer={footer} /></div>

      {confirmExit && (
        <div role="dialog" aria-modal="true" aria-labelledby="exit-title" className="fixed inset-0 z-40 flex items-end justify-center bg-[#0c0812]/70 p-4 backdrop-blur-sm sm:items-center">
          <div className="mat-parchment w-full max-w-sm rounded-3xl p-6 text-center">
            <Foxy pose="oops" size={110} className="mx-auto" />
            <h2 id="exit-title" className="mt-3 text-[22px] font-extrabold text-ink">Выйти из урока?</h2>
            <p className="mt-1 text-[16px] font-semibold text-ink-soft">Прогресс этого урока не сохранится.</p>
            <div className="mt-5 flex flex-col gap-3">
              <Button block onClick={() => setConfirmExit(false)} autoFocus>Продолжить урок</Button>
              <Button block variant="paper" onClick={() => router.push("/learn")}>Выйти</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
