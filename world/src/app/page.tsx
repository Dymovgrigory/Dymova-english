"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { GameButton } from "@/ui/Button";
import { greetingLine, isFirstSession, loadJourney, saveJourney } from "@/lib/journey";

const HERO = "/world/cinematic/establishing.jpg";
const GATE = "/world/cinematic/gates-foxi.jpg";

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [ready, setReady] = useState(false);
  const journey = useMemo(() => (ready ? loadJourney() : null), [ready]);
  const returning = Boolean(journey?.name && journey.lessonsFinished > 0);

  useEffect(() => {
    // localStorage доступен только в браузере: читаем один раз после гидрации.
    const j = loadJourney();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (j.name) setName(j.name);
    setReady(true);
  }, []);

  const enter = (href: string) => {
    const chosen = name.trim() || "Исследователь";
    saveJourney({ name: chosen });
    router.push(href);
  };

  const line = greetingLine(name.trim() || journey?.name || "друг", {
    isFirstSession: journey ? isFirstSession(journey) : true,
    streak: 0,
  });

  return (
    <main className="relative min-h-dvh overflow-hidden text-white">
      <div
        aria-hidden
        className="world-arrive absolute inset-0 bg-[#241a30] bg-cover bg-center"
        style={{ backgroundImage: `url(${returning ? GATE : HERO})` }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#241a30] via-[#241a30]/50 to-[#241a30]/15" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(127,216,201,0.18),_transparent_55%)]" />
      <div aria-hidden className="world-embers absolute inset-0" />

      <div className="relative z-10 mx-auto flex min-h-dvh w-full max-w-3xl flex-col justify-end px-5 pb-10 pt-16 md:justify-center md:pb-16">
        <p className="font-[family-name:var(--font-display)] text-[11px] font-bold uppercase tracking-[0.35em] text-[#f5ed75] drop-shadow">
          Foxinburg
        </p>
        <h1 className="mt-3 max-w-xl font-[family-name:var(--font-display)] text-4xl font-extrabold leading-[1.05] drop-shadow-md md:text-6xl">
          {returning ? "Снова в замке" : "Мир, где говорят вслух"}
        </h1>
        <p className="mt-4 max-w-md text-base font-semibold leading-relaxed text-white/85 md:text-lg">
          {returning ? line : "Foxy ждёт у ворот. Скажи слово — и Фоксинбург ответит."}
        </p>

        {!returning ? (
          <label className="mt-8 block max-w-md">
            <span className="sr-only">Как тебя зовут?</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Как тебя зовут?"
              className="w-full rounded-2xl border border-white/20 bg-[#241a30]/55 px-5 py-4 text-center text-lg font-bold text-white outline-none backdrop-blur-md placeholder:text-white/45 focus:border-[#f5ed75]"
              autoComplete="nickname"
            />
          </label>
        ) : null}

        <div className="mt-6 flex max-w-md flex-col gap-3">
          <GameButton onClick={() => enter("/learn")}>
            {returning ? "Сегодняшняя миссия" : "Войти в мир"}
          </GameButton>
          <button
            type="button"
            onClick={() => enter("/world")}
            className="rounded-2xl border border-white/25 bg-white/5 py-3 text-sm font-extrabold text-[#f5ed75] backdrop-blur-sm transition hover:bg-white/10"
          >
            {returning ? "Открыть замок" : "Сначала взглянуть на замок"}
          </button>
        </div>
      </div>
    </main>
  );
}
