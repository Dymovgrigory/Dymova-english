"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { worldApi } from "@/lib/api";
import { playCorrect, playWrong } from "@/lib/sfx";
import { recordLessonFinish } from "@/lib/journey";

type Card = { en: string; ru: string; image: string };

export default function SprintPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);
  const [reward, setReward] = useState<{ xp_delta: number; coins_delta: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [left, setLeft] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(45);

  useEffect(() => {
    const name = window.localStorage.getItem("world.name") || "Исследователь";
    void worldApi
      .ensurePlayer(name)
      .then(() => worldApi.getSprint())
      .then((body) => {
        setCards(body.words);
        setLeft(body.words[0]?.en ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Игра не открылась"));
  }, []);

  useEffect(() => {
    if (done || !cards.length) return;
    const id = window.setInterval(() => {
      setSeconds((n) => {
        if (n <= 1) {
          window.clearInterval(id);
          setDone(true);
          return 0;
        }
        return n - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [cards.length, done]);

  useEffect(() => {
    if (!done || reward) return;
    void worldApi
      .finishSprint(score, cards.length)
      .then((r) => {
        setReward(r);
        recordLessonFinish({ practice: true, itemsGranted: false, dueAfter: 0 });
      })
      .catch(() => setReward({ xp_delta: 0, coins_delta: 0 }));
  }, [done, reward, score, cards.length]);

  const options = useMemo(() => {
    if (!cards.length) return [];
    const want = cards[index];
    const pool = cards.filter((c) => c.en !== want?.en);
    const mix = [want, ...pool.slice(0, 3)].filter(Boolean) as Card[];
    return mix.sort((a, b) => a.en.localeCompare(b.en));
  }, [cards, index]);

  const pick = (en: string) => {
    if (done || !cards[index]) return;
    const ok = en === cards[index].en;
    if (ok) {
      playCorrect();
      setScore((n) => n + 1);
    } else playWrong();
    if (index + 1 >= cards.length) setDone(true);
    else {
      setIndex(index + 1);
      setLeft(cards[index + 1].en);
    }
  };

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#241a30] p-6 text-white">
      <div
        aria-hidden
        className="absolute inset-0 bg-cover bg-center opacity-45"
        style={{ backgroundImage: "url(/world/cinematic/establishing.jpg)" }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#241a30] via-[#241a30]/75 to-[#241a30]/40" />
      <div aria-hidden className="world-embers absolute inset-0" />

      <div className="relative z-10 w-full max-w-md text-center">
        <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">Двор · скорость</p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-extrabold text-[#f5ed75]">
          Найди картинку
        </h1>
        {error ? <p className="mt-3 text-sm text-[#ee7349]">{error}</p> : null}
        {!done ? (
          <>
            <p className="mt-2 font-bold text-white/85">
              {left} · {seconds}с · {score}/{cards.length}
            </p>
            <ul className="mt-6 grid grid-cols-2 gap-3">
              {options.map((card) => (
                <li key={card.en}>
                  <button
                    type="button"
                    onClick={() => pick(card.en)}
                    className="grid min-h-28 w-full place-items-center rounded-2xl border border-white/15 bg-[#241a30]/70 p-3 shadow-[0_6px_0_rgba(0,0,0,0.35)] backdrop-blur-md"
                    aria-label={card.ru || card.en}
                  >
                    {card.image ? (
                      <img src={card.image} alt="" className="h-24 w-24 object-contain" />
                    ) : (
                      <span className="font-extrabold text-[#f5ed75]">{card.ru}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="world-reward-pop mt-6 grid gap-3">
            <p className="text-xl font-extrabold">
              {score} из {cards.length}
            </p>
            {reward ? (
              <p className="font-bold text-[#7fd8c9]">
                +{reward.xp_delta} XP · +{reward.coins_delta} FoxCoins
              </p>
            ) : null}
            <Link
              href="/world?pulse=yard"
              className="rounded-2xl bg-[#f5ed75] py-4 font-extrabold text-[#241a30] shadow-[0_5px_0_rgba(0,0,0,0.35)]"
            >
              В замок за наградой
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
