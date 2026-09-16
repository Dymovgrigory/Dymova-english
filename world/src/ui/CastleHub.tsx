"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BUILDINGS, CASTLE_MAP, TIER_RU, isCastleDusk, type BuildingId } from "@/castle/buildings";
import { worldApi, type League, type Player, type ReviewQueue } from "@/lib/api";

type WordRow = { en: string; ru: string; ipa: string; image?: string; strength: number; unit: string };
type ShopItem = { sku: string; coins: number; title_ru: string };
type Quest = { id?: string; title_ru: string; progress: number; target: number; done: boolean };
type Sticker = { id: string; title_ru: string; emoji: string; owned: boolean };

function playerName() {
  if (typeof window === "undefined") return "Исследователь";
  return window.localStorage.getItem("world.name") || "Исследователь";
}

export function CastleHub() {
  const [room, setRoom] = useState<BuildingId | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [hearts, setHearts] = useState(5);
  const [lessonId, setLessonId] = useState("family-L1");
  const [league, setLeague] = useState<League | null>(null);
  const [review, setReview] = useState<ReviewQueue | null>(null);
  const [shop, setShop] = useState<ShopItem[]>([]);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [stickers, setStickers] = useState<Sticker[]>([]);
  const [stickerOwned, setStickerOwned] = useState(0);
  const [words, setWords] = useState<WordRow[]>([]);
  const [shopMsg, setShopMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [artOk, setArtOk] = useState<Record<string, boolean>>({});

  const load = () => {
    const name = playerName();
    void worldApi
      .ensurePlayer(name)
      .then(() =>
        Promise.all([
          worldApi.getLearnHome(),
          worldApi.getLearnPath(),
          worldApi.getShop(),
          worldApi.getLeague().catch(() => null),
          worldApi.getReview().catch(() => null),
        ]),
      )
      .then(([home, path, shopBody, leagueBody, reviewBody]) => {
        setError(null);
        setReview(reviewBody);
        setPlayer(home.player);
        setHearts(home.hearts?.current ?? 5);
        setLessonId(home.current_lesson_id || "family-L1");
        setQuests(home.quests || []);
        setStickers(home.stickers?.items || []);
        setStickerOwned(home.stickers?.owned ?? 0);
        setShop(shopBody.items);
        setLeague(leagueBody || home.league || null);
        const units = path.units.slice(0, 8).map((u) => u.id);
        return Promise.all(units.map((id) => worldApi.getWords(id).then((w) => ({ id, w })).catch(() => null)));
      })
      .then((packs) => {
        const rows: WordRow[] = [];
        for (const pack of packs || []) {
          if (!pack) continue;
          for (const w of pack.w.words) rows.push({ ...w, unit: pack.id });
        }
        setWords(rows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Замок не открылся. Запусти make world-dev."));
  };

  useEffect(() => {
    load();
  }, []);

  const learned = useMemo(() => words.filter((w) => w.strength > 0), [words]);
  const showWords = learned.length ? learned : words.slice(0, 24);
  const due = useMemo(() => new Set((review?.words || []).map((w) => w.en)), [review]);
  const dueCount = review?.due ?? 0;
  const active = BUILDINGS.find((b) => b.id === room);

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#7ec8ea] text-[#241a30]">
      <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 px-4 py-3">
        <Link href="/learn" className="rounded-full bg-white/90 px-4 py-2 text-sm font-extrabold shadow-[0_4px_0_rgba(36,26,48,0.12)]">
          К урокам
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-sm font-extrabold">
          <span className="rounded-full bg-[#f5ed75] px-3 py-1 shadow-[0_3px_0_rgba(36,26,48,0.12)]">🪙 {player?.coins ?? 0}</span>
          <span className="rounded-full bg-white px-3 py-1">⚡ {player?.xp ?? 0}</span>
          <span className="rounded-full bg-white px-3 py-1">♥ {hearts}</span>
        </div>
      </header>

      <div className="mx-auto flex min-h-dvh max-w-6xl flex-col justify-center px-3 pb-28 pt-16">
        <h1 className="mb-2 text-center font-[family-name:var(--font-display)] text-3xl font-extrabold text-[#3a2953] drop-shadow-sm md:text-4xl">
          Замок Фоксинбург
        </h1>
        <p className="mb-4 text-center text-sm font-semibold text-[#3a2953]/70">Нажми на здание — зайдёшь внутрь</p>
        {error ? <p className="mb-3 text-center text-sm text-[#ee7349]">{error}</p> : null}

        <div className="relative mx-auto w-full max-w-5xl">
          <img
            src={CASTLE_MAP}
            alt="Замок Фоксинбург сверху"
            className={`w-full select-none ${isCastleDusk() ? "brightness-90 contrast-110 saturate-125 hue-rotate-[-12deg]" : ""}`}
            draggable={false}
          />
          {BUILDINGS.map((b) => (
            <button
              key={b.id}
              type="button"
              aria-label={`${b.title}. ${b.hint}`}
              onClick={() => setRoom(b.id)}
              className="group absolute min-h-11 min-w-11 rounded-[22px] border-2 border-transparent hover:border-[#f5ed75] hover:bg-[#f5ed75]/20 focus:border-[#f5ed75] focus:outline-none"
              style={{
                left: `${b.box.left}%`,
                top: `${b.box.top}%`,
                width: `${b.box.width}%`,
                height: `${b.box.height}%`,
              }}
            >
              <span className="pointer-events-none absolute left-1/2 top-full z-10 mt-1 hidden -translate-x-1/2 whitespace-nowrap rounded-full bg-[#3a2953] px-3 py-1 text-xs font-extrabold text-[#f5ed75] shadow-lg group-hover:block group-focus:block">
                {b.title}
              </span>
            </button>
          ))}
        </div>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-20 overflow-x-auto border-t border-[#3a2953]/10 bg-[#f7f1e4]/95 px-3 py-3 backdrop-blur">
        <ul className="mx-auto flex w-max max-w-full gap-2">
          {BUILDINGS.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => setRoom(b.id)}
                className="rounded-full bg-[#3a2953] px-3 py-2 text-xs font-extrabold text-[#f5ed75]"
              >
                {b.title}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {active ? (
        <div className="fixed inset-0 z-40 grid place-items-end bg-[#241a30]/45 p-0 md:place-items-center md:p-6">
          <article className="relative flex h-[92dvh] w-full max-w-3xl flex-col overflow-hidden rounded-t-[28px] bg-[#f7f1e4] shadow-2xl md:h-auto md:max-h-[90dvh] md:rounded-[28px]">
            <div className="relative h-52 shrink-0 overflow-hidden bg-[#7ec8ea] md:h-64">
              <img
                src={artOk[active.art] === false ? CASTLE_MAP : active.art}
                alt=""
                className="h-full w-full object-cover object-center"
                onError={() => setArtOk((m) => ({ ...m, [active.art]: false }))}
                onLoad={() => setArtOk((m) => ({ ...m, [active.art]: true }))}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#241a30]/80 to-transparent" />
              <button
                type="button"
                onClick={() => setRoom(null)}
                className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-full bg-white text-xl font-extrabold text-[#3a2953]"
                aria-label="Закрыть"
              >
                ×
              </button>
              <div className="absolute bottom-3 left-4 right-16 text-white">
                <p className="font-[family-name:var(--font-display)] text-2xl font-extrabold">{active.title}</p>
                <p className="text-sm font-semibold text-white/80">{active.hint}</p>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {room === "school" ? (
                <div className="grid gap-3">
                  <p className="font-semibold leading-relaxed">Foxy ждёт у доски. Уроки — это учёба, замок — награда после них.</p>
                  <Link
                    href={`/learn/${lessonId}`}
                    className="rounded-2xl bg-[#3a2953] py-4 text-center text-lg font-extrabold text-[#f5ed75] shadow-[0_5px_0_#241a30]"
                  >
                    Войти в урок
                  </Link>
                  <Link href="/learn" className="rounded-2xl border-2 border-[#3a2953] py-3 text-center font-extrabold">
                    Карта всех уроков
                  </Link>
                </div>
              ) : null}

              {room === "shop" ? (
                <div className="grid gap-2">
                  {shop.map((item) => (
                    <button
                      key={item.sku}
                      type="button"
                      className="flex items-center justify-between rounded-2xl border border-[#241a30]/10 bg-white px-4 py-3 text-left font-extrabold"
                      onClick={() => {
                        void worldApi
                          .buyShop(item.sku)
                          .then((r) => {
                            setPlayer(r.player);
                            setShopMsg(r.items_granted?.length ? "Стикер в альбоме!" : "Куплено");
                            load();
                          })
                          .catch((err) => setShopMsg(err instanceof Error ? err.message : "Не хватило монет"));
                      }}
                    >
                      <span>{item.title_ru}</span>
                      <span>🪙 {item.coins}</span>
                    </button>
                  ))}
                  {shopMsg ? <p className="text-sm font-bold text-[#ee7349]">{shopMsg}</p> : null}
                </div>
              ) : null}

              {room === "glory" ? (
                <div className="grid gap-4">
                  <p className="rounded-2xl bg-[#3a2953] px-4 py-4 text-center font-[family-name:var(--font-display)] text-2xl font-extrabold text-[#f5ed75]">
                    {TIER_RU[league?.tier || "bronze"] || "Лига"}
                  </p>
                  <ul className="grid gap-2 text-sm font-bold">
                    <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                      <span>XP за неделю</span>
                      <span>{league?.weekly_xp ?? 0}</span>
                    </li>
                    <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                      <span>Место в лиге</span>
                      <span>
                        {league?.rank ?? 1} / {league?.size ?? 1}
                      </span>
                    </li>
                    <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                      <span>Всего XP</span>
                      <span>{player?.xp ?? 0}</span>
                    </li>
                    <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                      <span>Стикеры</span>
                      <span>{stickerOwned}</span>
                    </li>
                  </ul>
                  {league?.top?.length ? (
                    <ol className="grid gap-2">
                      {league.top.map((row) => (
                        <li
                          key={`${row.rank}-${row.display_name}`}
                          className={`flex justify-between rounded-2xl px-4 py-3 text-sm font-bold ${row.is_me ? "bg-[#f5ed75]" : "bg-white"}`}
                        >
                          <span>
                            {row.rank}. {row.display_name}
                          </span>
                          <span>{row.weekly_xp} XP</span>
                        </li>
                      ))}
                    </ol>
                  ) : null}
                </div>
              ) : null}

              {room === "lexicon" ? (
                <div className="grid gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-[#3a2953] px-4 py-3 text-sm font-extrabold text-[#f5ed75]">
                    <span>Выучено слов: {learned.length}</span>
                    <span>{dueCount > 0 ? `Пора повторить: ${dueCount}` : "Всё свежее"}</span>
                  </div>
                  {dueCount > 0 ? (
                    <Link
                      href="/learn/practice"
                      className="rounded-2xl bg-[#f5ed75] py-3 text-center font-extrabold text-[#241a30] shadow-[0_4px_0_rgba(36,26,48,0.18)]"
                    >
                      Повторить {dueCount} {dueCount === 1 ? "слово" : "слов"}
                    </Link>
                  ) : null}
                  <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {showWords.map((w) => (
                      <li
                        key={`${w.unit}-${w.en}`}
                        className={`overflow-hidden rounded-2xl text-center ${due.has(w.en) ? "bg-[#f5ed75]" : "bg-white"}`}
                      >
                        {w.image ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={w.image}
                            alt={w.en}
                            className="mx-auto mt-2 h-20 w-20 object-contain"
                            loading="lazy"
                          />
                        ) : null}
                        <div className="p-3 pt-1">
                          <p className="font-[family-name:var(--font-display)] text-lg font-extrabold text-[#3a2953]">{w.en}</p>
                          {w.ipa ? <p className="text-xs font-bold text-[#3a2953]/50">{w.ipa}</p> : null}
                          <p className="mt-1 text-[11px] font-semibold text-[#241a30]/45">
                            {due.has(w.en) ? "пора повторить" : w.strength ? `сила ${w.strength} из 5` : "ещё впереди"}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {room === "stickers" ? (
                <ul className="grid grid-cols-3 gap-2">
                  {stickers.map((it) => (
                    <li
                      key={it.id}
                      className={`rounded-2xl border bg-white p-3 text-center ${it.owned ? "border-[#f5ed75]" : "opacity-40 grayscale"}`}
                    >
                      <p className="text-3xl">{it.emoji}</p>
                      <p className="mt-1 text-[11px] font-extrabold">{it.title_ru}</p>
                    </li>
                  ))}
                </ul>
              ) : null}

              {room === "nest" ? (
                <ul className="grid gap-2 text-sm font-bold">
                  <li className="rounded-2xl bg-white px-4 py-3">{player?.display_name || "Исследователь"}</li>
                  <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                    <span>Уровень</span>
                    <span>
                      {player?.level_title_ru || player?.level_title} · {player?.level}
                    </span>
                  </li>
                  <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                    <span>Серия дней</span>
                    <span>🔥 {player?.streak_days ?? 0}</span>
                  </li>
                  <li className="flex justify-between rounded-2xl bg-white px-4 py-3">
                    <span>Сердца</span>
                    <span>♥ {hearts}</span>
                  </li>
                </ul>
              ) : null}

              {room === "quests" ? (
                <ul className="grid gap-2">
                  {quests.map((q) => (
                    <li key={q.title_ru} className="flex justify-between rounded-2xl bg-white px-4 py-3 text-sm font-bold">
                      <span>
                        {q.done ? "✓ " : ""}
                        {q.title_ru}
                      </span>
                      <span className="text-[#241a30]/45">
                        {q.progress}/{q.target}
                      </span>
                    </li>
                  ))}
                  <Link href={`/learn/${lessonId}`} className="mt-2 rounded-2xl bg-[#3a2953] py-3 text-center font-extrabold text-[#f5ed75]">
                    Выполнить поручение
                  </Link>
                </ul>
              ) : null}

              {room === "yard" ? (
                <div className="grid gap-3">
                  <p className="font-semibold">
                    {dueCount > 0
                      ? `Foxy отложил ${dueCount} слов на сегодня — самое время их вспомнить.`
                      : "Сегодня всё свежее. Можно потренировать слова из текущего урока."}
                  </p>
                  <Link
                    href="/learn/practice"
                    className="rounded-2xl bg-[#3a2953] py-4 text-center text-lg font-extrabold text-[#f5ed75]"
                  >
                    {dueCount > 0 ? `Повторить ${dueCount}` : "Тренировка"}
                  </Link>
                  <Link
                    href="/learn/sprint"
                    className="rounded-2xl border-2 border-[#3a2953] py-3 text-center font-extrabold"
                  >
                    Игра на скорость
                  </Link>
                  <Link href={`/learn/${lessonId}`} className="rounded-2xl border-2 border-[#3a2953] py-3 text-center font-extrabold">
                    Открыть текущий урок
                  </Link>
                </div>
              ) : null}
            </div>
          </article>
        </div>
      ) : null}
    </main>
  );
}
