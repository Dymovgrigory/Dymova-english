"use client";

import { useEffect, useRef, useState } from "react";

import type { FoxiHandle } from "./engine";
import { walkDurationMs, walkFacing, walkStartTransform, type WalkOffset } from "./walk";

/**
 * Живой 3D-Фокси рядом с окном текущего урока (этап 4, STYLE_LOCK «3D-маскот Фокси»).
 * Стоит слева от окна на «карнизе», не закрывая ни окно, ни подпись, ни ряд выше.
 * При смене текущего узла (проп walkFrom) ПРОХОДИТ от старого окна к новому:
 * DOM-анимация translate контейнера + клип Walking и разворот в движке.
 * SSR/LCP-фолбэк — статичный webp; three.js и GLB грузятся после idle,
 * только когда маскот виден. prefers-reduced-motion, отсутствие WebGL или
 * ошибка загрузки → webp БЕЗ ходьбы. Кнопка «Спрятать Фокси» — localStorage,
 * возврат через кнопку «Позвать Фокси».
 */

const HIDE_KEY = "world-foxi-hidden";

function StaticFoxi() {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- фолбэк-маскот (статичный кадр)
    <img
      src="/content/foxy/wave.webp"
      alt=""
      className="pointer-events-none absolute -left-[52px] top-[24px] z-10 h-14 w-14 object-contain drop-shadow-[0_4px_6px_rgb(0_0_0/0.6)]"
    />
  );
}

export function FoxiMascot({ walkFrom = null }: { walkFrom?: WalkOffset | null }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const walkerRef = useRef<HTMLDivElement>(null);
  const foxiRef = useRef<FoxiHandle | null>(null);
  // null — до монтирования (SSR: webp), дальше webp | canvas | hidden
  const [mode, setMode] = useState<"webp" | "canvas" | "hidden" | null>(null);
  const [prompt, setPrompt] = useState(false);
  // Стартовое смещение перехода; null — стоим у окна
  const [offset, setOffset] = useState<WalkOffset | null>(walkFrom);
  const walking = offset !== null && walkDurationMs(offset) > 0;
  // Ходьба началась — грузим движок сразу, не дожидаясь IntersectionObserver/idle:
  // иначе на холодной загрузке GLB лис невидим всю дорогу между окнами
  const kickBootRef = useRef<(() => void) | null>(null);

  // Tower считает смещение после монтирования (нужны ref-ы окон) — подхватываем
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- триггер FLIP-анимации по пропсу
    setOffset((prev) => (walkFrom && !prev ? walkFrom : prev));
  }, [walkFrom]);

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

  // Ходьба: FLIP — стартуем со смещения старого окна, в следующем кадре
  // включаем transition к (0,0); движок получает направление и длительность.
  useEffect(() => {
    if (!walking || !offset) return;
    const el = walkerRef.current;
    const duration = walkDurationMs(offset);
    const facing = walkFacing(offset);
    if (el) {
      kickBootRef.current?.();
      el.dataset.walkStartedAt = String(performance.now());
      el.style.transform = walkStartTransform(offset);
      el.getBoundingClientRect(); // принудительный reflow: браузер фиксирует стартовую точку до transition
      const raf = requestAnimationFrame(() => {
        el.style.transition = `transform ${duration}ms cubic-bezier(0.45, 0.05, 0.35, 1)`;
        el.style.transform = "translate(0px, 0px)";
      });
      const done = window.setTimeout(() => setOffset(null), duration + 100);
      // Если движок уже загружен — включаем походку сразу; иначе onReady доберёт
      foxiRef.current?.walk(facing, duration);
      return () => {
        cancelAnimationFrame(raf);
        window.clearTimeout(done);
      };
    }
  }, [walking, offset]);

  useEffect(() => {
    if (mode !== "canvas") return;
    const host = hostRef.current;
    if (!host) return;

    let cancelled = false;
    let io: IntersectionObserver | null = null;
    let booted = false;

    const boot = () => {
      if (cancelled) return;
      import("./engine")
        .then(({ createFoxi }) =>
          createFoxi(host, {
            onPrompt: setPrompt,
            onReady: () => {
              if (cancelled) return;
              // Движок поднялся в середине перехода — догоняем остаток походки
              const el = walkerRef.current;
              if (el && offset) {
                const duration = walkDurationMs(offset);
                const startedAt = Number(el.dataset.walkStartedAt ?? 0);
                const left = duration - (performance.now() - startedAt);
                // DOM-переход уже кончился к подъёму движка (холодная загрузка GLB) —
                // всё равно приветствуем и показываем бабл
                if (left > 250) foxiRef.current?.walk(walkFacing(offset), left);
                else foxiRef.current?.greet();
              }
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

    // GLB грузим только когда маскот виден, и после idle — не бьём LCP;
    // kickBootRef (старт походки) включает загрузку сразу, минуя observer и idle
    const startBoot = () => {
      if (booted || cancelled) return;
      booted = true;
      io?.disconnect();
      const ric = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 800));
      ric(boot);
    };
    kickBootRef.current = startBoot;
    // Походка могла начаться в этом же коммите раньше (эффект ходьбы объявлен выше)
    if (walkerRef.current?.dataset.walkStartedAt) startBoot();
    io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) startBoot();
    });
    io.observe(host);

    const onCelebrate = () => foxiRef.current?.celebrate();
    const onDance = () => foxiRef.current?.dance();
    window.addEventListener("foxi:celebrate", onCelebrate);
    window.addEventListener("foxi:dance", onDance);

    return () => {
      cancelled = true;
      kickBootRef.current = null;
      io?.disconnect();
      window.removeEventListener("foxi:celebrate", onCelebrate);
      window.removeEventListener("foxi:dance", onDance);
      foxiRef.current?.dispose();
      foxiRef.current = null;
    };
    // offset в deps не нужен: бут один раз на смену режима; остаток походки читается из DOM
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        className="absolute -left-10 top-6 z-10 rounded-full bg-black/55 px-2 py-0.5 text-[11px] font-extrabold text-[#ffd36e] ring-1 ring-white/15 transition hover:bg-black/75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffd36e]"
      >
        Позвать Фокси
      </button>
    );
  }

  return (
    <div
      ref={walkerRef}
      className="pointer-events-none absolute -left-[104px] top-[3px] z-10 h-[112px] w-[112px] will-change-transform"
    >
      <div ref={hostRef} className="relative h-full w-full" data-testid="foxi3d-host" />
      {prompt && (
        <div
          role="status"
          aria-live="polite"
          className="absolute -top-7 left-1/2 z-20 -translate-x-1/2 whitespace-nowrap rounded-2xl rounded-bl-sm bg-[#fff2b8] px-2.5 py-1 text-[12px] font-extrabold text-[#3a2208] shadow-[0_4px_10px_rgb(0_0_0/0.45)] ring-2 ring-[#9a6414]/50"
        >
          Нажми на следующий урок!
        </div>
      )}
      <button
        type="button"
        onClick={hide}
        aria-label="Спрятать Фокси"
        className="pointer-events-auto absolute -right-1 -top-1 z-20 flex size-5 items-center justify-center rounded-full bg-black/55 text-[12px] font-black text-[#c9bfd8] ring-1 ring-white/15 transition hover:bg-black/75 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffd36e]"
      >
        ×
      </button>
    </div>
  );
}
