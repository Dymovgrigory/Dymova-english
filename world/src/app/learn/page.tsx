"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { worldApi, type LearnPath, type LearnUnit, type Player } from "@/lib/api";
import { FoxiGuide } from "@/ui/FoxiGuide";
import { WorldBar } from "@/ui/WorldBar";
import { LearnTrail } from "@/ui/LearnTrail";
import { SkyWash } from "@/ui/Fx";

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
  const [quests, setQuests] = useState<{ title_ru: string; progress: number; target: number; done: boolean }[]>([]);
  const [shop, setShop] = useState<{ sku: string; coins: number; title_ru: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [shopMsg, setShopMsg] = useState<string | null>(null);
  const [due, setDue] = useState(0);

  const load = () => {
    let name = "Исследователь";
    try {
      name = window.localStorage.getItem("world.name") || name;
    } catch {
      /* private mode */
    }
    void worldApi
      .ensurePlayer(name)
      .then(() =>
        Promise.all([
          worldApi.getLearnPath(),
          worldApi.getLearnHome(),
          worldApi.getShop(),
          worldApi.getReview().catch(() => null),
        ]),
      )
      .then(([data, home, shopBody, reviewBody]) => {
        setError(null);
        setPath(data);
        setPlayer(home.player);
        setStickers(home.stickers.owned);
        setQuests(home.quests);
        setShop(shopBody.items);
        setDue(reviewBody?.due ?? 0);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Курс не загрузился. Запусти make world-dev — UI :3002, API :8010."));
  };

  useEffect(() => {
    load();
  }, []);

  const here = useMemo(() => (path ? currentLessonId(path.units) : null), [path]);
  const hearts = path?.hearts ?? 5;

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#f7f1e4] text-[#241a30]">
      <SkyWash />
      <header className="sticky top-0 z-20 border-b border-[#241a30]/10 bg-[#f7f1e4]/80 px-4 py-3 backdrop-blur">
        <WorldBar
          hearts={hearts}
          player={player}
          stickers={stickers}
          streak={player?.streak_days}
          coins={player?.coins}
          xp={player?.xp}
        />
      </header>

      <div className="relative z-10 mx-auto max-w-2xl px-4 pb-24 pt-6">
        <FoxiGuide
          pose="wave"
          kicker="Foxy"
          line="Я твой учитель. Собирай монетки и стикеры. Говори вслух — я слушаю."
        />
        <h1 className="mt-5 text-3xl font-extrabold leading-tight">1 класс: Foxy учит</h1>
        {player?.level_title_ru ? (
          <p className="mt-2 text-sm font-bold text-[#3a2953]">
            {player.level_title_ru} · уровень {player.level}
          </p>
        ) : null}
        {path?.unlock_all ? (
          <p className="mt-3 rounded-2xl bg-[#3a2953] px-4 py-2 text-center text-xs font-extrabold text-[#f5ed75]">
            Все модули открыты — гуляй по курсу
          </p>
        ) : null}
        <Link
          href={here ? `/learn/${here}` : "/learn/family-L1"}
          className="mt-6 inline-flex w-full items-center justify-center rounded-2xl bg-[#3a2953] py-4 text-lg font-extrabold text-[#f5ed75] shadow-[0_6px_0_#241a30] transition active:translate-y-0.5 active:shadow-none"
        >
          {here ? "Продолжить с Foxy" : "Начать · Привет!"}
        </Link>
        <Link
          href="/learn/practice"
          className={`mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-[#3a2953] py-3 text-base font-extrabold text-[#3a2953] ${
            due > 0 ? "bg-[#f5ed75]" : "bg-white"
          }`}
        >
          Двор тренировки
          {due > 0 ? (
            <span className="rounded-full bg-[#3a2953] px-2 py-0.5 text-xs font-extrabold text-[#f5ed75]">{due}</span>
          ) : null}
        </Link>
        <Link
          href="/world"
          className="mt-3 inline-flex w-full items-center justify-center rounded-2xl border-2 border-[#3a2953] bg-white py-3 text-base font-extrabold text-[#3a2953]"
        >
          В замок Фоксинбург
        </Link>

        {error ? <p className="mt-6 text-sm text-[#ee7349]">{error}</p> : null}
        {!path && !error ? <p className="mt-8 text-[#241a30]/40">Открываем тетрадь…</p> : null}

        <LearnTrail units={path?.units ?? []} here={here} />

        {quests.length ? (
          <section className="mt-6 rounded-3xl border border-[#241a30]/10 bg-white p-5">
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#241a30]/40">Сегодня</p>
            <ul className="mt-3 space-y-2">
              {quests.map((q) => (
                <li key={q.title_ru} className="flex justify-between text-sm font-bold">
                  <span>{q.done ? "✓ " : ""}{q.title_ru}</span>
                  <span className="text-[#241a30]/45">
                    {q.progress}/{q.target}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {shop.length ? (
          <section className="mt-4 rounded-3xl border border-[#241a30]/10 bg-white p-5">
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#241a30]/40">Лавка Фокси</p>
            <div className="mt-3 grid gap-2">
              {shop.map((item) => (
                <button
                  key={item.sku}
                  type="button"
                  className="flex items-center justify-between rounded-2xl border border-[#241a30]/10 px-4 py-3 text-left text-sm font-extrabold"
                  onClick={() => {
                    void worldApi
                      .buyShop(item.sku)
                      .then((r) => {
                        setPlayer(r.player);
                        setShopMsg(r.items_granted?.length ? "Стикер в альбоме!" : "Готово");
                        load();
                      })
                      .catch((err) => setShopMsg(err instanceof Error ? err.message : "Не хватило монет"));
                  }}
                >
                  <span>{item.title_ru}</span>
                  <span>🪙 {item.coins}</span>
                </button>
              ))}
            </div>
            {shopMsg ? <p className="mt-2 text-xs text-[#ee7349]">{shopMsg}</p> : null}
            <Link href="/learn/album" className="mt-3 inline-block text-sm font-bold text-[#3a2953]">
              Альбом стикеров →
            </Link>
          </section>
        ) : null}

        <section className="mt-8 rounded-3xl border border-dashed border-[#241a30]/20 bg-white/60 p-5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-[#241a30]/40">Дальше в этом пути</p>
          <h2 className="mt-1 text-xl font-extrabold">Учимся читать</h2>
          <p className="mt-2 text-sm leading-relaxed text-[#241a30]/65">
            {path?.next_book_ru ||
              "После шести модулей 1 класса откроются звуки: sat, pin, dog — Фокси останется учителем."}
          </p>
        </section>
      </div>
    </main>
  );
}
