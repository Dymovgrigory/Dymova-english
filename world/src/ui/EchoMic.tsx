"use client";

import { echoPass, echoScore } from "@/lib/echo";
import { stopSpeaking } from "@/lib/speak";
import { useEffect, useRef, useState } from "react";

type Props = {
  target?: string;
  onPass?: () => void;
  /** Речь недоступна (нет движка, нет разрешения) или ребёнок честно застрял — не запирать урок. */
  onBlocked?: (reason: string) => void;
};

/** Столько попыток даём, прежде чем открыть кнопку «Дальше» без удачного повтора. */
const MAX_TRIES = 5;

type Rec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function recognitionCtor(): (new () => Rec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function EchoMic({ target, onPass, onBlocked }: Props) {
  const [state, setState] = useState<"idle" | "listen" | "ok" | "retry">("idle");
  const [hint, setHint] = useState("");
  const [level, setLevel] = useState(0);
  const [fails, setFails] = useState(0);
  const alive = useRef(true);
  const busy = useRef(false);
  // Сброс на новом слове делает родитель через key — эффект-ресет здесь не нужен.
  const tries = useRef(0);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  if (!target) return null;

  const finishOk = (text: string) => {
    busy.current = false;
    tries.current = 0;
    setFails(0);
    setLevel(0);
    setHint(text);
    setState("ok");
    onPass?.();
  };

  const finishRetry = (text: string) => {
    busy.current = false;
    setLevel(0);
    tries.current += 1;
    setFails(tries.current);
    setHint(text);
    setState("retry");
    if (tries.current >= MAX_TRIES) onBlocked?.("tries");
  };

  const finishBlocked = (reason: string, text: string) => {
    onBlocked?.(reason);
    finishRetry(text);
  };

  const listen = async () => {
    if (busy.current) return;
    busy.current = true;
    stopSpeaking();
    setState("listen");
    setHint(`Говори 3 секунды: ${target}`);
    setLevel(0.25);

    const Ctor = recognitionCtor();
    if (!Ctor) {
      finishBlocked("unsupported", "Этот браузер не слышит речь. Открой Chrome или Safari — а пока идём дальше.");
      return;
    }

    await new Promise((r) => window.setTimeout(r, 280));

    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 3;

    let heard = "";
    let blocked = "";
    let raf = 0;
    const t0 = performance.now();
    const pulse = () => {
      const t = (performance.now() - t0) / 180;
      if (alive.current) setLevel(0.22 + 0.4 * Math.abs(Math.sin(t)));
      raf = requestAnimationFrame(pulse);
    };
    raf = requestAnimationFrame(pulse);

    const heardText = await new Promise<string>((resolve) => {
      let settled = false;
      const finish = (text: string) => {
        if (settled) return;
        settled = true;
        try {
          rec.stop();
        } catch {
          /* already stopped */
        }
        resolve(text);
      };

      rec.onresult = (ev) => {
        const last = ev.results[ev.results.length - 1];
        const text = (last?.[0]?.transcript || "").trim();
        if (!text) return;
        heard = text;
        if (echoPass(echoScore(heard, target))) finish(heard);
      };
      rec.onerror = (ev) => {
        const err = ev.error || "";
        if (err === "not-allowed") {
          blocked = "not-allowed";
          finish("");
          return;
        }
        if (err === "audio-capture") {
          blocked = "audio-capture";
          finish("");
        }
      };
      rec.onend = () => {
        if (settled) return;
        if (performance.now() - t0 < 3000) {
          try {
            rec.start();
          } catch {
            /* engine still running */
          }
        }
      };
      try {
        rec.start();
      } catch {
        finish("");
      }
      window.setTimeout(() => finish(heard), 3600);
    });

    cancelAnimationFrame(raf);
    if (!alive.current) {
      busy.current = false;
      return;
    }

    if (blocked === "not-allowed") {
      finishBlocked("not-allowed", "Разреши микрофон в адресной строке — тогда Foxy тебя услышит.");
      return;
    }
    if (blocked === "audio-capture") {
      finishBlocked("audio-capture", "Микрофон занят. Закрой другие вкладки со звуком и нажми ещё раз.");
      return;
    }

    const said = heardText.trim();
    if (!said) {
      finishRetry(`Не услышал фразу. Говори сразу после «Слушаю» и держи 2–3 секунды: ${target}`);
      return;
    }
    if (echoPass(echoScore(said, target))) {
      finishOk(`Верно. Foxy услышал: ${said}`);
      return;
    }
    finishRetry(`Ты сказал «${said}». Нужно: ${target}`);
  };

  const label =
    state === "listen" ? "Слушаю…" : state === "ok" ? "Есть!" : state === "retry" ? "Ещё раз" : "Скажи как Foxy";

  return (
    <div className="mt-2 grid justify-items-center gap-2">
      <button
        type="button"
        onClick={() => void listen()}
        disabled={state === "listen"}
        className={`relative overflow-hidden rounded-full px-6 py-3.5 text-sm font-extrabold shadow-[0_4px_0_rgba(36,26,48,0.18)] ${
          state === "ok"
            ? "bg-[#7fd8c9] text-[#13332c]"
            : state === "listen"
              ? "bg-[#3a2953] text-[#f5ed75]"
              : state === "retry"
                ? "bg-[#ee7349] text-white"
                : "bg-[#f5ed75] text-[#241a30]"
        }`}
      >
        {state === "listen" ? <span className="absolute inset-0 animate-pulse rounded-full bg-[#f5ed75]/20" /> : null}
        <span className="relative">🎙️ {label}</span>
      </button>
      {state === "listen" ? (
        <span className="flex h-3 w-36 overflow-hidden rounded-full bg-[#3a2953]/15">
          <span
            className="h-full rounded-full bg-[#f5ed75] transition-[width] duration-75"
            style={{ width: `${Math.min(100, 10 + level * 280)}%` }}
          />
        </span>
      ) : null}
      {hint ? <p className="max-w-[18rem] text-center text-xs font-bold text-[#3a2953]/70">{hint}</p> : null}
      {state === "retry" && fails >= 2 && fails < MAX_TRIES ? (
        <p className="max-w-[18rem] text-center text-[11px] font-semibold text-[#3a2953]/50">
          Нужен Chrome или Safari, английская диктовка и интернет. Говори сразу, не шепчи.
        </p>
      ) : null}
      {fails >= MAX_TRIES ? (
        <p className="max-w-[18rem] text-center text-[11px] font-semibold text-[#3a2953]/50">
          Идём дальше. Скажи это слово маме после урока — Foxy поверит.
        </p>
      ) : null}
    </div>
  );
}
