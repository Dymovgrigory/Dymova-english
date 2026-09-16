"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BUILDINGS, CASTLE_MAP, MAP_VIEWBOX, TIER_RU, type BuildingId } from "@/castle/buildings";
import { worldApi, type League, type Player, type ReviewQueue } from "@/lib/api";
import { castleNudgeLine, loadJourney, markCastleIntroSeen } from "@/lib/journey";

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
  const [hovered, setHovered] = useState<BuildingId | null>(null);
  const [debugHotspots, setDebugHotspots] = useState(false);
  const [debugPoint, setDebugPoint] = useState<{ x: number; y: number } | null>(null);
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
  const [pulse, setPulse] = useState<BuildingId | null>(null);
  const [pulseNote, setPulseNote] = useState<string | null>(null);
  const [nudge, setNudge] = useState<string | null>(null);

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDebugHotspots(params.get("debugHotspots") === "1");

    const journey = loadJourney();
    setNudge(castleNudgeLine(journey));
    if (journey.lessonsFinished <= 0) return;

    const queryPulse = params.get("pulse");
    const pulseId = BUILDINGS.find((b) => b.id === queryPulse)?.id ?? journey.lastRewardBuilding;
    if (!pulseId || !BUILDINGS.some((b) => b.id === pulseId)) return;

    setPulse(pulseId);
    const title = BUILDINGS.find((b) => b.id === pulseId)?.title || "здание";
    setPulseNote(pulseId === "nest" ? "Твоё гнездо — ты растёшь в замке" : `Foxy подсветил: ${title}`);
    markCastleIntroSeen();
    const t = window.setTimeout(() => setPulse(null), 6500);
    return () => window.clearTimeout(t);
  }, []);

  const learned = useMemo(() => words.filter((w) => w.strength > 0), [words]);
  const showWords = learned.length ? learned : words.slice(0, 24);
  const due = useMemo(() => new Set((review?.words || []).map((w) => w.en)), [review]);
  const dueCount = review?.due ?? 0;
  const active = BUILDINGS.find((b) => b.id === room);
  const hoverBuilding = BUILDINGS.find((b) => b.id === hovered);
  const pulseBuilding = BUILDINGS.find((b) => b.id === pulse);
  const labelBuilding = hoverBuilding || (pulseBuilding && !room ? pulseBuilding : null);

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#1a1230] text-white">
      {/* One scene: cinematic map IS the world — no second photo plate. */}
      <div className="absolute inset-0">
        <svg
          className="h-full w-full select-none"
          viewBox={`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`}
          preserveAspectRatio="xMidYMid slice"
          role="group"
          aria-label="Интерактивные здания замка"
          onClick={
            debugHotspots
              ? (e) => {
                  const svg = e.currentTarget;
                  const pt = svg.createSVGPoint();
                  pt.x = e.clientX;
                  pt.y = e.clientY;
                  const ctm = svg.getScreenCTM();
                  if (!ctm) return;
                  const local = pt.matrixTransform(ctm.inverse());
                  const x = Math.round(local.x);
                  const y = Math.round(local.y);
                  setDebugPoint({ x, y });
                  console.info(`[castle hotspot] ${x},${y}`);
                }
              : undefined
          }
        >
          <title>Замок Фоксинбург</title>
          <image href={CASTLE_MAP} width={MAP_VIEWBOX.width} height={MAP_VIEWBOX.height} />
          <defs>
            <filter id="castle-glow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#f5ed75" floodOpacity="0.95" />
            </filter>
            <filter id="castle-teal" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#7fd8c9" floodOpacity="0.9" />
            </filter>
          </defs>
          {BUILDINGS.map((b) => {
            const isHovered = hovered === b.id;
            const isPulse = pulse === b.id;
            const lit = isHovered || debugHotspots || isPulse;
            let fill = "rgba(245,237,117,0)";
            if (isHovered || isPulse) fill = isPulse ? "rgba(127,216,201,0.28)" : "rgba(245,237,117,0.34)";
            else if (debugHotspots) fill = "rgba(245,237,117,0.14)";
            return (
              <polygon
                key={b.id}
                points={b.polygon}
                fill={fill}
                stroke={lit ? (isPulse ? "#7fd8c9" : "#f5ed75") : "rgba(245,237,117,0)"}
                strokeWidth={isHovered || isPulse ? 5 : debugHotspots ? 2.5 : 0}
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
                filter={isPulse ? "url(#castle-teal)" : isHovered ? "url(#castle-glow)" : undefined}
                className={`cursor-pointer outline-none transition-[fill,stroke] duration-100 ${isPulse ? "world-pulse-ring" : ""}`}
                onMouseEnter={() => setHovered(b.id)}
                onMouseLeave={() => setHovered((h) => (h === b.id ? null : h))}
                onFocus={() => setHovered(b.id)}
                onBlur={() => setHovered((h) => (h === b.id ? null : h))}
                onClick={() => setRoom(b.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setRoom(b.id);
                  }
                }}
                tabIndex={0}
                role="button"
                aria-label={`${b.title}. ${b.hint}`}
              />
            );
          })}
          {debugPoint ? (
            <g pointerEvents="none">
              <circle cx={debugPoint.x} cy={debugPoint.y} r={6} fill="#f5ed75" stroke="#3a2953" strokeWidth={2} />
              <text
                x={debugPoint.x + 10}
                y={debugPoint.y - 10}
                fill="#f5ed75"
                stroke="#3a2953"
                strokeWidth={3}
                paintOrder="stroke"
                fontSize={22}
                fontWeight={800}
              >
                {debugPoint.x},{debugPoint.y}
              </text>
            </g>
          ) : null}
        </svg>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-36 bg-gradient-to-b from-[#241a30]/75 via-[#241a30]/25 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#241a30]/85 via-[#241a30]/35 to-transparent"
      />
      <div aria-hidden className="world-embers pointer-events-none absolute inset-0 opacity-50" />

      <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 px-4 py-3">
        <Link
          href="/learn"
          className="rounded-full border border-white/15 bg-[#241a30]/55 px-4 py-2 text-sm font-extrabold text-[#f5ed75] backdrop-blur-md shadow-[0_4px_0_rgba(0,0,0,0.25)]"
        >
          К урокам
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-sm font-extrabold">
          <span className="rounded-full bg-[#f5ed75] px-3 py-1 text-[#241a30] shadow-[0_3px_0_rgba(0,0,0,0.25)]">
            🪙 {player?.coins ?? 0}
          </span>
          <span className="rounded-full border border-white/15 bg-[#241a30]/55 px-3 py-1 text-white backdrop-blur-md">
            ⚡ {player?.xp ?? 0}
          </span>
          <span className="rounded-full border border-white/15 bg-[#241a30]/55 px-3 py-1 text-white backdrop-blur-md">
            ♥ {hearts}
          </span>
        </div>
      </header>

      <div className="pointer-events-none absolute inset-x-0 top-16 z-20 px-4 text-center md:top-20">
        <p className="text-[11px] font-bold uppercase tracking-[0.35em] text-[#7fd8c9] drop-shadow">Foxinburg</p>
        <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl font-extrabold text-[#f5ed75] drop-shadow-md md:text-4xl">
          Замок Фоксинбург
        </h1>
        <p className="mt-1 text-sm font-semibold text-white/85 drop-shadow">
          {pulseNote || nudge || "Нажми на здание — зайдёшь внутрь"}
        </p>
        {nudge && !pulseNote ? (
          <Link
            href={`/learn/${lessonId}`}
            className="pointer-events-auto mt-3 inline-flex rounded-2xl bg-[#f5ed75] px-5 py-2.5 text-sm font-extrabold text-[#241a30] shadow-[0_4px_0_rgba(0,0,0,0.35)]"
          >
            К уроку с Foxy
          </Link>
        ) : null}
        {error ? <p className="mt-2 text-sm text-[#ee7349]">{error}</p> : null}
        {debugHotspots ? (
          <p className="mt-2 text-xs font-bold text-[#f5ed75]">
            Debug hotspots
            {debugPoint ? ` · ${debugPoint.x},${debugPoint.y}` : ""}
          </p>
        ) : null}
      </div>

      {labelBuilding ? (
        <div className="pointer-events-none absolute bottom-28 left-1/2 z-20 -translate-x-1/2 rounded-full bg-[#3a2953]/90 px-3 py-1 text-xs font-extrabold text-[#f5ed75] shadow-lg backdrop-blur">
          {labelBuilding.title}
        </div>
      ) : null}

      <nav className="fixed inset-x-0 bottom-0 z-20 overflow-x-auto border-t border-white/10 bg-[#241a30]/75 px-3 py-3 backdrop-blur-md">
        <ul className="mx-auto flex w-max max-w-full gap-2">
          {BUILDINGS.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => setRoom(b.id)}
                className={`rounded-full px-3 py-2 text-xs font-extrabold ${
                  pulse === b.id
                    ? "bg-[#7fd8c9] text-[#13332c] shadow-[0_0_0_3px_rgba(127,216,201,0.35)]"
                    : "bg-[#3a2953]/90 text-[#f5ed75]"
                }`}
              >
                {b.title}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {active ? (
        <div className="fixed inset-0 z-40 flex flex-col bg-[#241a30]">
          <div className="absolute inset-0">
            <img
              src={artOk[active.art] === false ? CASTLE_MAP : active.art}
              alt=""
              className="h-full w-full object-cover object-center brightness-[0.92] contrast-110 saturate-125"
              onError={() => setArtOk((m) => ({ ...m, [active.art]: false }))}
              onLoad={() => setArtOk((m) => ({ ...m, [active.art]: true }))}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#241a30]/96 via-[#241a30]/50 to-[#241a30]/20" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(127,216,201,0.12),_transparent_55%)]" />
          </div>

          <div className="relative z-10 flex items-start justify-between gap-3 px-4 pb-2 pt-4">
            <div className="max-w-xl text-white drop-shadow-md">
              <p className="font-[family-name:var(--font-display)] text-2xl font-extrabold md:text-3xl">{active.title}</p>
              <p className="text-sm font-semibold text-white/85">{active.hint}</p>
            </div>
            <button
              type="button"
              onClick={() => setRoom(null)}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white text-xl font-extrabold text-[#3a2953] shadow-lg"
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>

          <div className="relative z-10 mt-auto max-h-[68dvh] overflow-y-auto rounded-t-[28px] border-t border-white/10 bg-[#241a30]/92 p-5 text-white shadow-[0_-12px_40px_rgba(0,0,0,0.45)] backdrop-blur-md">
            {room === "school" ? (
              <div className="grid gap-3">
                <p className="font-semibold leading-relaxed text-white/85">
                  Foxy ждёт у доски. Уроки — это учёба, замок — награда после них.
                </p>
                <Link
                  href={`/learn/${lessonId}`}
                  className="rounded-2xl bg-[#f5ed75] py-4 text-center text-lg font-extrabold text-[#241a30] shadow-[0_5px_0_rgba(0,0,0,0.35)]"
                >
                  Войти в урок
                </Link>
                <Link
                  href="/learn"
                  className="rounded-2xl border border-white/20 bg-white/5 py-3 text-center font-extrabold text-[#f5ed75]"
                >
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
                    className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-left font-extrabold text-white"
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
                    <span className="text-[#f5ed75]">🪙 {item.coins}</span>
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
                  <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                    <span>XP за неделю</span>
                    <span>{league?.weekly_xp ?? 0}</span>
                  </li>
                  <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                    <span>Место в лиге</span>
                    <span>
                      {league?.rank ?? 1} / {league?.size ?? 1}
                    </span>
                  </li>
                  <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                    <span>Всего XP</span>
                    <span>{player?.xp ?? 0}</span>
                  </li>
                  <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                    <span>Стикеры</span>
                    <span>{stickerOwned}</span>
                  </li>
                </ul>
                {league?.top?.length ? (
                  <ol className="grid gap-2">
                    {league.top.map((row) => (
                      <li
                        key={`${row.rank}-${row.display_name}`}
                        className={`flex justify-between rounded-2xl px-4 py-3 text-sm font-bold ${row.is_me ? "bg-[#f5ed75] text-[#241a30]" : "bg-white/10"}`}
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
                    className="rounded-2xl bg-[#f5ed75] py-3 text-center font-extrabold text-[#241a30] shadow-[0_4px_0_rgba(0,0,0,0.25)]"
                  >
                    Повторить {dueCount} {dueCount === 1 ? "слово" : "слов"}
                  </Link>
                ) : null}
                <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {showWords.map((w) => (
                    <li
                      key={`${w.unit}-${w.en}`}
                      className={`overflow-hidden rounded-2xl text-center ${due.has(w.en) ? "bg-[#f5ed75] text-[#241a30]" : "bg-white/10"}`}
                    >
                      {w.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={w.image} alt={w.en} className="mx-auto mt-2 h-20 w-20 object-contain" loading="lazy" />
                      ) : null}
                      <div className="p-3 pt-1">
                        <p className="font-[family-name:var(--font-display)] text-lg font-extrabold">{w.en}</p>
                        {w.ipa ? <p className="text-xs font-bold opacity-60">{w.ipa}</p> : null}
                        <p className="mt-1 text-[11px] font-semibold opacity-50">
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
                    className={`rounded-2xl border p-3 text-center ${it.owned ? "border-[#f5ed75] bg-[#f5ed75]/15" : "border-white/10 bg-white/5 opacity-40 grayscale"}`}
                  >
                    <p className="text-3xl">{it.emoji}</p>
                    <p className="mt-1 text-[11px] font-extrabold">{it.title_ru}</p>
                  </li>
                ))}
              </ul>
            ) : null}

            {room === "nest" ? (
              <ul className="grid gap-2 text-sm font-bold">
                <li className="rounded-2xl bg-white/10 px-4 py-3">{player?.display_name || "Исследователь"}</li>
                <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                  <span>Уровень</span>
                  <span>
                    {player?.level_title_ru || player?.level_title} · {player?.level}
                  </span>
                </li>
                <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                  <span>Серия дней</span>
                  <span>🔥 {player?.streak_days ?? 0}</span>
                </li>
                <li className="flex justify-between rounded-2xl bg-white/10 px-4 py-3">
                  <span>Сердца</span>
                  <span>♥ {hearts}</span>
                </li>
              </ul>
            ) : null}

            {room === "quests" ? (
              <ul className="grid gap-2">
                {quests.map((q) => (
                  <li key={q.title_ru} className="flex justify-between rounded-2xl bg-white/10 px-4 py-3 text-sm font-bold">
                    <span>
                      {q.done ? "✓ " : ""}
                      {q.title_ru}
                    </span>
                    <span className="text-white/45">
                      {q.progress}/{q.target}
                    </span>
                  </li>
                ))}
                <Link
                  href={`/learn/${lessonId}`}
                  className="mt-2 rounded-2xl bg-[#f5ed75] py-3 text-center font-extrabold text-[#241a30]"
                >
                  Выполнить поручение
                </Link>
              </ul>
            ) : null}

            {room === "yard" ? (
              <div className="grid gap-3">
                <p className="font-semibold text-white/85">
                  {dueCount > 0
                    ? `Foxy отложил ${dueCount} слов на сегодня — самое время их вспомнить.`
                    : "Сегодня всё свежее. Можно потренировать слова из текущего урока."}
                </p>
                <Link
                  href="/learn/practice"
                  className="rounded-2xl bg-[#f5ed75] py-4 text-center text-lg font-extrabold text-[#241a30]"
                >
                  {dueCount > 0 ? `Повторить ${dueCount}` : "Тренировка"}
                </Link>
                <Link
                  href="/learn/sprint"
                  className="rounded-2xl border border-white/20 bg-white/5 py-3 text-center font-extrabold text-[#f5ed75]"
                >
                  Игра на скорость
                </Link>
                <Link
                  href={`/learn/${lessonId}`}
                  className="rounded-2xl border border-white/20 bg-white/5 py-3 text-center font-extrabold text-white/85"
                >
                  Открыть текущий урок
                </Link>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  );
}
