"use client";

import { useEffect, useMemo, useState } from "react";
import { worldApi, type Player } from "@/lib/api";
import { playCorrect, playWrong } from "@/lib/sfx";
import { recordLessonFinish } from "@/lib/journey";
import { RoomCta, RoomKicker, RoomLead, RoomTitle } from "@/ui/RoomChrome";
import { WorldBar } from "@/ui/WorldBar";

type Card = { en: string; ru: string; image: string };

export default function SprintPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);
  const [reward, setReward] = useState<{
    xp_delta: number;
    coins_delta: number;
    daily_xp?: number;
    daily_goal?: number;
    cosmetic_only?: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [left, setLeft] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(45);
  const [player, setPlayer] = useState<Player | null>(null);
  const [hearts, setHearts] = useState(5);
  const [stickers, setStickers] = useState(0);

  useEffect(() => {
    const name = window.localStorage.getItem("world.name") || "Исследователь";
    void worldApi
      .ensurePlayer(name)
      .then(() => Promise.all([worldApi.getSprint(), worldApi.getLearnHome().catch(() => null)]))
      .then(([body, home]) => {
        setCards(body.words);
        setSessionId(body.session_id);
        setLeft(body.words[0]?.en ?? null);
        if (home) {
          setPlayer(home.player);
          setHearts(home.hearts?.current ?? 5);
          setStickers(home.stickers?.owned ?? 0);
        }
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
    if (!done || reward || !sessionId) return;
    void worldApi
      .finishSprint(sessionId, score, cards.length)
      .then((r) => {
        setReward(r);
        if (r.player) setPlayer(r.player);
        recordLessonFinish({ practice: true, itemsGranted: false, dueAfter: 0 });
      })
      .catch(() => setReward({ xp_delta: 0, coins_delta: 0, cosmetic_only: true }));
  }, [done, reward, score, cards.length, sessionId]);

  const options = useMemo(() => {
    if (!cards.length) return [];
    const want = cards[index];
    const pool = cards.filter((c) => c.en !== want?.en);
    const mix = [want, ...pool.slice(0, 3)].filter(Boolean) as Card[];
    return mix.sort((a, b) => a.en.localeCompare(b.en));
  }, [cards, index]);

  const pick = (en: string) => {
    if (done || !cards[index] || !sessionId) return;
    const prompt = cards[index].en;
    void worldApi
      .answerSprint(sessionId, prompt, en)
      .then((r) => {
        if (r.correct) {
          playCorrect();
          setScore(r.score);
        } else playWrong();
      })
      .catch(() => playWrong());
    if (index + 1 >= cards.length) setDone(true);
    else {
      setIndex(index + 1);
      setLeft(cards[index + 1].en);
    }
  };

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#241a30] p-6 text-white">
      <header className="absolute inset-x-0 top-0 z-20 px-4 py-3">
        <WorldBar hearts={hearts} player={player} stickers={stickers} xp={player?.xp} coins={player?.coins} />
      </header>
      <div
        aria-hidden
        className="absolute inset-0 bg-cover bg-center opacity-45"
        style={{ backgroundImage: "url(/world/cinematic/establishing.png)" }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#241a30] via-[#241a30]/75 to-[#241a30]/40" />
      <div aria-hidden className="world-embers absolute inset-0" />

      <div className="relative z-10 w-full max-w-md pt-14 text-center">
        <RoomKicker>Двор · скорость</RoomKicker>
        <RoomTitle>Найди картинку</RoomTitle>
        <RoomLead>Успей выбрать верный след слова.</RoomLead>
        {error ? <p className="mt-3 text-sm text-[#ee7349]">{error}</p> : null}
        {!done ? (
          <>
            <p className="mt-3 font-[family-name:var(--font-display)] text-lg font-extrabold text-[#f5ed75]">
              {left} · {seconds}с · {score}/{cards.length}
            </p>
            <ul className="mt-6 grid grid-cols-2 gap-3">
              {options.map((card) => (
                <li key={card.en}>
                  <button
                    type="button"
                    onClick={() => pick(card.en)}
                    className="grid min-h-28 w-full place-items-center rounded-2xl border border-white/15 bg-[#241a30]/70 p-3 shadow-[0_6px_0_rgba(0,0,0,0.35)] backdrop-blur-md transition hover:scale-[1.02]"
                    aria-label={card.ru || card.en}
                  >
                    {card.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
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
          <div className="world-reward-pop mt-8 space-y-4">
            <p className="font-[family-name:var(--font-display)] text-2xl font-extrabold text-[#f5ed75]">
              {score} из {cards.length}
              {reward ? ` · +${reward.xp_delta} XP` : ""}
            </p>
            {reward?.cosmetic_only ? (
              <p className="text-sm text-white/70">Без серверных ответов награда не начисляется.</p>
            ) : null}
            <RoomCta href="/world?pulse=yard">В замок за наградой</RoomCta>
          </div>
        )}
      </div>
    </main>
  );
}
