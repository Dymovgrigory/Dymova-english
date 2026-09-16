"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { worldApi, type LearnPath, type LearnUnit, type NextBestAction, type Player } from "@/lib/api";
import { FoxiGuide } from "@/ui/FoxiGuide";
import { WorldBar } from "@/ui/WorldBar";
import { LearnTrail } from "@/ui/LearnTrail";
import { greetingLine, isFirstSession, loadJourney, missionFor, syncProgressFromServer, type JourneyState } from "@/lib/journey";

function currentLessonId(units: LearnUnit[]): string | null {
  for (const unit of units) {
    for (const lesson of unit.lessons) {
      if (!lesson.locked && lesson.stars === 0) return lesson.id;
    }
  }
  return units.flatMap((u) => u.lessons).find((l) => !l.locked)?.id ?? null;
}

export default function LearnPathPage() {
  const [path, setPath] = useState<LearnPath | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [stickers, setStickers] = useState(0);
  const [quests, setQuests] = useState<{ id?: string; title_ru: string; progress: number; target: number; done: boolean; claimable?: boolean; claimed?: boolean }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [due, setDue] = useState(0);
  const [name, setName] = useState("Исследователь");
  const [journey, setJourney] = useState<JourneyState | null>(null);
  const [nba, setNba] = useState<NextBestAction | null>(null);

  const load = () => {
    let stored = "Исследователь";
    try {
      stored = window.localStorage.getItem("world.name") || loadJourney().name || stored;
    } catch {
      /* private mode */
    }
    setName(stored);
    void worldApi
      .ensurePlayer(stored)
      .then(() =>
        Promise.all([
          worldApi.getLearnPath(),
          worldApi.getLearnHome(),
          worldApi.getReview().catch(() => null),
        ]),
      )
      .then(([data, home, reviewBody]) => {
        setError(null);
        setPath(data);
        setPlayer(home.player);
        setStickers(home.stickers.owned);
        setQuests(home.quests);
        setDue(reviewBody?.due ?? 0);
        setNba(home.next_best_action ?? null);
        const synced = syncProgressFromServer({
          lessonsStarred: home.lessons_starred ?? 0,
          name: home.player?.display_name || stored,
          level: home.player?.level,
        });
        setJourney(synced);
        if (synced.name) setName(synced.name);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Курс не загрузился. Запусти make world-dev."));
  };

  useEffect(() => {
    // Имя и journey живут в localStorage — читаем после гидрации, чтобы SSR-разметка совпала.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJourney(loadJourney());
    load();
  }, []);

  const here = useMemo(() => (path ? currentLessonId(path.units) : null), [path]);
  const hearts = path?.hearts ?? 5;
  const fallback = missionFor({
    due,
    nextLessonId: here,
    lessonsFinished: journey?.lessonsFinished,
    claimable: quests.filter((q) => q.claimable).length,
  });
  const mission = nba
    ? {
        kind: (nba.kind === "quest" ? "castle" : nba.kind === "review" ? "practice" : "lesson") as
          | "castle"
          | "practice"
          | "lesson",
        href: nba.href,
        title: nba.title,
        hint: nba.hint,
      }
    : fallback;
  const greets = greetingLine(name, {
    isFirstSession: journey ? isFirstSession(journey) : true,
    streak: player?.streak_days ?? 0,
  });
  const sideHref = due > 0 ? `/learn/${here || "family-L1"}` : "/learn/practice";
  const sideLabel = due > 0 ? "Урок" : "Двор";

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#241a30] text-white">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[52vh] bg-cover bg-center opacity-90"
        style={{ backgroundImage: "url(/world/learn-ui-hero.png)" }}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[52vh] bg-gradient-to-b from-[#241a30]/35 via-[#241a30]/55 to-[#241a30]" />
      <div aria-hidden className="world-embers pointer-events-none absolute inset-x-0 top-0 h-[52vh]" />

      <header className="relative z-20 px-4 py-3">
        <WorldBar
          hearts={hearts}
          player={player}
          stickers={stickers}
          streak={player?.streak_days}
          coins={player?.coins}
          xp={player?.xp}
        />
      </header>

      <div className="relative z-10 mx-auto max-w-2xl px-4 pb-24 pt-4">
        <FoxiGuide pose="wave" kicker="Foxy" line={greets} tone="dark" />

        <section className="mt-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-[#f5ed75]">Сегодня</p>
          <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-extrabold leading-tight md:text-4xl">
            {mission.title}
          </h1>
          <p className="mt-2 text-sm font-semibold text-white/75">{mission.hint}</p>
          {nba?.why ? <p className="mt-1 text-xs font-medium text-white/50">{nba.why}</p> : null}
          <Link
            href={mission.href}
            data-analytic-id={nba?.analytic_id ?? "world.school.startLesson"}
            className="mt-5 inline-flex w-full items-center justify-center border border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] py-4 text-lg font-extrabold text-[#241a30] shadow-[0_5px_0_#9a7a18] transition active:translate-y-0.5 active:shadow-none"
            style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
          >
            {mission.kind === "castle"
              ? "Забрать в беседке"
              : mission.kind === "practice"
                ? "Войти во двор"
                : "Начать с Foxy"}
          </Link>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Link
              href="/world"
              className="border border-[#f5ed75]/35 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] py-3 text-center text-sm font-extrabold text-[#f5ed75]"
              style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
            >
              Замок
            </Link>
            <Link
              href={sideHref}
              className="border border-[#7fd8c9]/35 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] py-3 text-center text-sm font-extrabold text-[#7fd8c9]"
              style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
            >
              {sideLabel}
            </Link>
          </div>
        </section>

        {error ? <p className="mt-6 text-sm text-[#ee7349]">{error}</p> : null}
        {!path && !error ? <p className="mt-8 text-white/40">Открываем тетрадь…</p> : null}

        <div
          className="mt-8 overflow-hidden border border-[#f5ed75]/20 bg-[#241a30]/90 p-4 text-white shadow-[0_-8px_40px_rgba(0,0,0,0.35)] backdrop-blur-md"
          style={{ clipPath: "polygon(2% 0, 98% 0, 100% 4%, 100% 96%, 98% 100%, 2% 100%, 0 96%, 0 4%)" }}
        >
          <p className="px-1 text-[11px] font-bold uppercase tracking-wider text-[#7fd8c9]/80">Путь 1 класса</p>
          <LearnTrail units={path?.units ?? []} here={here} />

          {quests.length ? (
            <section
              className="mt-4 overflow-hidden border border-[#f5ed75]/25 bg-[#3a2953]/55 p-4"
              style={{ clipPath: "polygon(3% 0, 97% 0, 100% 8%, 100% 92%, 97% 100%, 3% 100%, 0 92%, 0 8%)" }}
            >
              <p className="text-[11px] font-bold uppercase tracking-wider text-[#7fd8c9]/80">Поручения</p>
              <ul className="mt-2 space-y-2">
                {quests.map((q) => (
                  <li key={q.id || q.title_ru} className="flex justify-between text-sm font-bold">
                    <span>
                      {q.done ? "✓ " : ""}
                      {q.title_ru}
                    </span>
                    <span className={q.claimable ? "text-[#f5ed75]" : "text-white/45"}>
                      {q.claimed ? "Получено" : q.claimable ? "Забрать" : `${q.progress}/${q.target}`}
                    </span>
                  </li>
                ))}
              </ul>
              {quests.some((q) => q.claimable) ? (
                <Link
                  href="/world?pulse=quests"
                  className="mt-3 inline-flex w-full items-center justify-center border border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] py-2.5 text-sm font-extrabold text-[#241a30]"
                  style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
                >
                  Забрать в беседке
                </Link>
              ) : null}
            </section>
          ) : null}

          <section
            className="mt-4 overflow-hidden border border-dashed border-[#7fd8c9]/25 bg-[#3a2953]/40 p-4"
            style={{ clipPath: "polygon(3% 0, 97% 0, 100% 8%, 100% 92%, 97% 100%, 3% 100%, 0 92%, 0 8%)" }}
          >
            <p className="text-[11px] font-bold uppercase tracking-wider text-white/40">Дальше</p>
            <h2 className="mt-1 text-lg font-extrabold text-[#f5ed75]">Учимся читать</h2>
            <p className="mt-1 text-sm leading-relaxed text-white/65">
              {path?.next_book_ru ||
                "После шести модулей 1 класса откроются звуки — Foxy останется учителем."}
            </p>
            <Link href="/learn/album" className="mt-3 inline-block text-sm font-bold text-[#7fd8c9]">
              Альбом стикеров →
            </Link>
          </section>
        </div>
      </div>
    </main>
  );
}
