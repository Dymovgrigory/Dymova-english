"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { worldApi } from "@/lib/api";
import { playCorrect, playWrong } from "@/lib/sfx";

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
    void worldApi.finishSprint(score, cards.length).then(setReward).catch(() => setReward({ xp_delta: 0, coins_delta: 0 }));
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
    <main className="grid min-h-dvh place-items-center bg-[#f7f1e4] p-6 text-[#241a30]">
      <div className="w-full max-w-md text-center">
        <p className="text-sm font-extrabold text-[#3a2953]/60">Двор · на скорость</p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-extrabold">Найди картинку</h1>
        {error ? <p className="mt-3 text-sm text-[#ee7349]">{error}</p> : null}
        {!done ? (
          <>
            <p className="mt-2 font-bold">
              {left} · {seconds}с · {score}/{cards.length}
            </p>
            <ul className="mt-6 grid grid-cols-2 gap-3">
              {options.map((card) => (
                <li key={card.en}>
                  <button
                    type="button"
                    onClick={() => pick(card.en)}
                    className="grid min-h-28 w-full place-items-center rounded-2xl bg-white p-3 shadow-[0_4px_0_rgba(36,26,48,0.12)]"
                    aria-label={card.ru || card.en}
                  >
                    {card.image ? (
                      <img src={card.image} alt="" className="h-24 w-24 object-contain" />
                    ) : (
                      <span className="font-extrabold text-[#3a2953]">{card.ru}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <div className="mt-6 grid gap-3">
            <p className="text-xl font-extrabold">
              {score} из {cards.length}
            </p>
            {reward ? (
              <p className="font-bold">
                +{reward.xp_delta} XP · +{reward.coins_delta} FoxCoins
              </p>
            ) : null}
            <Link href="/world" className="rounded-2xl bg-[#3a2953] py-4 font-extrabold text-[#f5ed75]">
              В замок
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
