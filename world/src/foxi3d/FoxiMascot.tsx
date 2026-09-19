"use client";

import { useEffect, useRef, useState } from "react";

import type { FoxiHandle } from "./engine";

/**
 * Живой 3D-Фокси над окном текущего урока (этап 4, STYLE_LOCK «3D-маскот Фокси»).
 * SSR/LCP-фолбэк — статичный webp; three.js и GLB грузятся после idle,
 * только когда маскот виден. prefers-reduced-motion, отсутствие WebGL или
 * ошибка загрузки → webp. Кнопка «Спрятать Фокси» — localStorage,
 * возврат через кнопку «Позвать Фокси».
 */

const HIDE_KEY = "world-foxi-hidden";

function StaticFoxi() {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- фолбэк-маскот (статичный кадр)
    <img
      src="/content/foxy/wave.webp"
      alt=""
      className="pointer-events-none absolute -top-10 left-1/2 z-10 h-12 w-12 -translate-x-1/2 object-contain drop-shadow-[0_4px_6px_rgb(0_0_0/0.6)]"
    />
  );
}

export function FoxiMascot() {
  const hostRef = useRef<HTMLDivElement>(null);
  const foxiRef = useRef<FoxiHandle | null>(null);
  // null — до монтирования (SSR: webp), дальше webp | canvas | hidden
  const [mode, setMode] = useState<"webp" | "canvas" | "hidden" | null>(null);
  const [prompt, setPrompt] = useState(false);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- выбор режима (webp/canvas/hidden) возможен только в браузере */
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setMode("webp");
      return;
    }
    if (window.localStorage.getItem(HIDE_KEY) === "1") {
      setMode("hidden");
      return;
    }
    setMode("canvas");
  }, []);

  useEffect(() => {
    if (mode !== "canvas") return;
    const host = hostRef.current;
    if (!host) return;

    let cancelled = false;
    let io: IntersectionObserver | null = null;

    const boot = () => {
      if (cancelled) return;
      import("./engine")
        .then(({ createFoxi }) =>
          createFoxi(host, {
            onPrompt: setPrompt,
            onReady: () => {
              if (cancelled) return;
              // Пульс: новый доступный урок (?pulse=...) — «ура» + короткий танец
              const q = new URLSearchParams(window.location.search).get("pulse");
              if (q) {
                foxiRef.current?.celebrate();
                if (Math.random() < 0.5) {
                  window.setTimeout(() => foxiRef.current?.dance(), 4500);
                }
              }
            },
            onError: () => {
              if (!cancelled) setMode("webp");
            },
          }),
        )
        .then((handle) => {
          if (cancelled) handle.dispose();
          else foxiRef.current = handle;
        })
        .catch(() => {
          if (!cancelled) setMode("webp");
        });
    };

    // GLB грузим только когда маскот виден, и после idle — не бьём LCP
    io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        io?.disconnect();
        const ric = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 800));
        ric(boot);
      }
    });
    io.observe(host);

    const onCelebrate = () => foxiRef.current?.celebrate();
    const onDance = () => foxiRef.current?.dance();
    window.addEventListener("foxi:celebrate", onCelebrate);
    window.addEventListener("foxi:dance", onDance);

    return () => {
      cancelled = true;
      io?.disconnect();
      window.removeEventListener("foxi:celebrate", onCelebrate);
      window.removeEventListener("foxi:dance", onDance);
      foxiRef.current?.dispose();
      foxiRef.current = null;
    };
  }, [mode]);

  const hide = () => {
    window.localStorage.setItem(HIDE_KEY, "1");
    setMode("hidden");
  };
  const restore = () => {
    window.localStorage.removeItem(HIDE_KEY);
    setMode("canvas");
  };

  if (mode === null || mode === "webp") return <StaticFoxi />;

  if (mode === "hidden") {
    return (
      <button
        type="button"
        onClick={restore}
        aria-label="Позвать Фокси обратно"
        className="absolute -top-8 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/55 px-2 py-0.5 text-[11px] font-extrabold text-[#ffd36e] ring-1 ring-white/15 transition hover:bg-black/75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffd36e]"
      >
        Позвать Фокси
      </button>
    );
  }

  return (
    <div className="pointer-events-none absolute -top-[150px] left-1/2 z-10 h-[150px] w-[190px] -translate-x-1/2">
      <div ref={hostRef} className="relative h-full w-full" data-testid="foxi3d-host" />
      {prompt && (
        <div
          role="status"
          aria-live="polite"
          className="absolute -top-2 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-2xl rounded-bl-sm bg-[#fff2b8] px-3 py-1.5 text-[13px] font-extrabold text-[#3a2208] shadow-[0_4px_10px_rgb(0_0_0/0.45)] ring-2 ring-[#9a6414]/50"
        >
          Нажми на следующий урок!
        </div>
      )}
      <button
        type="button"
        onClick={hide}
        aria-label="Спрятать Фокси"
        className="pointer-events-auto absolute right-0 top-0 z-20 flex size-6 items-center justify-center rounded-full bg-black/55 text-[13px] font-black text-[#c9bfd8] ring-1 ring-white/15 transition hover:bg-black/75 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffd36e]"
      >
        ×
      </button>
    </div>
  );
}
