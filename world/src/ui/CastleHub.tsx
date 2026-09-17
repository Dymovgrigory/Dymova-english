"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BUILDINGS, CASTLE_MAP, MAP_VIEWBOX, TIER_RU, type BuildingId } from "@/castle/buildings";
import { worldApi, type League, type NextBestAction, type Player, type ReviewQueue } from "@/lib/api";
import { castleNudgeLine, loadJourney, markCastleIntroSeen, syncProgressFromServer } from "@/lib/journey";
import {
  BrandIcon,
  FantasyHudChip,
  FantasyNavChip,
  RoomCta,
  RoomHeader,
  RoomKicker,
  RoomLead,
  RoomRelic,
  RoomSheet,
  RoomTile,
  RoomTitle,
} from "@/ui/RoomChrome";
import { StickerCollection, StickerPreviewRow } from "@/ui/fantasy/StickerDrawer";

type WordRow = { en: string; ru: string; ipa: string; image?: string; strength: number; unit: string };
type ShopItem = { sku: string; coins: number; title_ru: string };
type Quest = { id?: string; title_ru: string; progress: number; target: number; done: boolean; claimed?: boolean; claimable?: boolean };
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
  const [questMsg, setQuestMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [artOk, setArtOk] = useState<Record<string, boolean>>({});
  const [pulse, setPulse] = useState<BuildingId | null>(null);
  const [pulseNote, setPulseNote] = useState<string | null>(null);
  const [nudge, setNudge] = useState<string | null>(null);
  const [nba, setNba] = useState<NextBestAction | null>(null);

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
        setNba(home.next_best_action ?? null);
        setQuests(home.quests || []);
        setStickers(home.stickers?.items || []);
        setStickerOwned(home.stickers?.owned ?? 0);
        setShop(shopBody.items);
        setLeague(leagueBody || home.league || null);
        syncProgressFromServer({
          lessonsStarred: home.lessons_starred ?? 0,
          name: home.player?.display_name,
          level: home.player?.level,
        });
        setNudge(castleNudgeLine(loadJourney()));
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
    if (queryPulse) setRoom(pulseId); // deep-link opens the room (e.g. finish → quests claim)
    const title = BUILDINGS.find((b) => b.id === pulseId)?.title || "здание";
    setPulseNote(
      pulseId === "quests"
        ? "Задания дня готовы — забери награду"
        : pulseId === "nest"
          ? "Твоё гнездо — ты растёшь в замке"
          : `Foxy подсветил: ${title}`,
    );
    markCastleIntroSeen();
    const t = window.setTimeout(() => setPulse(null), 6500);
    return () => window.clearTimeout(t);
  }, []);

  const learned = useMemo(() => words.filter((w) => w.strength > 0), [words]);
  const showWords = learned.length ? learned : words.slice(0, 24);
  const due = useMemo(() => new Set((review?.words || []).map((w) => w.en)), [review]);
  const claimableQuests = useMemo(() => quests.filter((q) => q.claimable).length, [quests]);
  const dueCount = review?.due ?? 0;
  const active = BUILDINGS.find((b) => b.id === room);
  const hoverBuilding = BUILDINGS.find((b) => b.id === hovered);
  const labelBuilding = hoverBuilding || (pulse ? BUILDINGS.find((b) => b.id === pulse) : null);

  return (
    <main className="relative min-h-[100dvh] overflow-hidden bg-[#1a1230] text-white">
      <div className="absolute inset-0 flex items-center justify-center">
        <svg
          viewBox={`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`}
          className="h-full w-full max-h-[100dvh] object-contain"
          role="img"
          aria-label="Карта замка Фоксинбург"
          onClick={(e) => {
            if (!debugHotspots) return;
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
          }}
        >
          <image href={CASTLE_MAP} width={MAP_VIEWBOX.width} height={MAP_VIEWBOX.height} />
          {BUILDINGS.map((b) => (
            <polygon
              key={b.id}
              points={b.polygon}
              fill={debugHotspots || hovered === b.id || pulse === b.id ? "rgba(245,237,117,0.18)" : "transparent"}
              stroke={debugHotspots || hovered === b.id || pulse === b.id ? "#f5ed75" : "transparent"}
              strokeWidth={debugHotspots || hovered === b.id || pulse === b.id ? 3 : 0}
              className="cursor-pointer"
              onMouseEnter={() => setHovered(b.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={(ev) => {
                ev.stopPropagation();
                setRoom(b.id);
              }}
            />
          ))}
          {labelBuilding ? (
            <foreignObject
              x={labelBuilding.label.x - 70}
              y={labelBuilding.label.y - 28}
              width={140}
              height={36}
              pointerEvents="none"
            >
              <div className="flex justify-center">
                <span
                  className="border border-[#f5ed75]/70 bg-[#3a2953]/95 px-3 py-1.5 text-center text-[13px] font-extrabold leading-none text-[#f5ed75] shadow-lg"
                  style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
                >
                  {labelBuilding.title}
                </span>
              </div>
            </foreignObject>
          ) : null}
        </svg>
      </div>

      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-36 bg-gradient-to-b from-[#241a30]/75 via-[#241a30]/25 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-44 bg-gradient-to-t from-[#241a30]/90 via-[#241a30]/40 to-transparent"
      />
      <div aria-hidden className="world-embers pointer-events-none absolute inset-0 opacity-50" />

      <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-3 px-3 py-3">
        <Link href="/learn" className="shrink-0">
          <span
            className="inline-flex min-h-[44px] items-center border border-[#f5ed75]/45 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] px-4 py-2 text-sm font-extrabold text-[#f5ed75] shadow-[0_4px_0_#1a1230]"
            style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
          >
            К урокам
          </span>
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <HudChip icon={<BrandIcon name="coin" className="!h-7 !w-7" />} value={player?.coins ?? 0} gold />
          <HudChip icon={<BrandIcon name="xp" className="!h-7 !w-7" />} value={player?.xp ?? 0} />
          <HudChip icon={<BrandIcon name="heart" className="!h-7 !w-7" />} value={hearts} />
        </div>
      </header>

      <div className="pointer-events-none absolute inset-x-0 top-16 z-20 flex justify-center px-4 md:top-20">
        <div
          className="max-w-md border border-[#f5ed75]/40 bg-[linear-gradient(165deg,rgba(58,41,83,0.88),rgba(36,26,48,0.92))] px-5 py-3 text-center shadow-[0_8px_28px_rgba(0,0,0,0.35)] backdrop-blur-md"
          style={{ clipPath: "polygon(4% 0, 96% 0, 100% 14%, 100% 86%, 96% 100%, 4% 100%, 0 86%, 0 14%)" }}
        >
          <p className="text-[10px] font-bold uppercase tracking-[0.32em] text-[#7fd8c9]">Foxinburg</p>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl font-extrabold text-[#f5ed75] md:text-3xl">
            Замок Фоксинбург
          </h1>
          <p className="mt-1 text-[12px] font-medium leading-snug text-white/85">
            {pulseNote || nudge || nba?.hint || "Нажми на здание — зайдёшь внутрь"}
          </p>
          {!pulseNote ? (
            <Link
              href="/learn"
              data-analytic-id={nba?.analytic_id ?? "world.school.startLesson"}
              className="pointer-events-auto mt-3 inline-flex min-h-[44px] items-center rounded-none border border-[#fff6a8]/55 bg-[linear-gradient(180deg,#f5ed75,#e8b93e)] px-5 py-2 text-sm font-extrabold text-[#241a30] shadow-[0_4px_0_#9a7a18]"
              style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
            >
              {nba?.title || "К уроку с Foxy"}
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
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-20 overflow-x-auto border-t border-[#f5ed75]/25 bg-[linear-gradient(180deg,rgba(36,26,48,0.75),rgba(26,18,40,0.95))] px-3 py-3 backdrop-blur-md">
        <ul className="mx-auto flex w-max max-w-full gap-2 pb-1">
          {BUILDINGS.map((b) => (
            <li key={b.id}>
              <FantasyNavChip active={room === b.id} pulse={pulse === b.id || (b.id === "quests" && claimableQuests > 0)} onClick={() => setRoom(b.id)}>
                {b.title}
              </FantasyNavChip>
            </li>
          ))}
        </ul>
      </nav>

      {active ? (
        <div className="fixed inset-0 z-40 flex flex-col bg-[#241a30]">
          <div className="absolute inset-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={artOk[active.art] === false ? CASTLE_MAP : active.art}
              alt=""
              className="h-full w-full object-cover object-center brightness-100 contrast-110 saturate-125"
              onError={() => setArtOk((m) => ({ ...m, [active.art]: false }))}
              onLoad={() => setArtOk((m) => ({ ...m, [active.art]: true }))}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#241a30]/55 via-transparent to-transparent" />
            <div aria-hidden className="world-embers absolute inset-0 opacity-15" />
          </div>

          <RoomHeader kicker="Foxinburg" title={active.title} hint={active.hint} onClose={() => setRoom(null)} />

          <RoomSheet>
            {room === "school" ? (
              <>
                <RoomKicker>Школа · врата знаний</RoomKicker>
                <RoomTitle>{nba?.kind === "lesson" ? nba.title : "Урок с Foxy"}</RoomTitle>
                {nba?.kind === "lesson" && nba.why ? <RoomLead>{nba.why}</RoomLead> : null}
                <RoomCta href="/learn">Войти в урок</RoomCta>
                <RoomCta href="/learn" tone="ghost">
                  Карта всех уроков
                </RoomCta>
              </>
            ) : null}

            {room === "shop" ? (
              <>
                <RoomKicker>Лавка · сокровища</RoomKicker>
                <RoomTitle>Витрина Фокси</RoomTitle>
                {shop.map((item) => (
                  <RoomTile
                    key={item.sku}
                    onClick={() => {
                      void worldApi
                        .buyShop(item.sku)
                        .then((r) => {
                          setPlayer(r.player);
                          if (typeof r.hearts === "number") setHearts(r.hearts);
                          setShopMsg(
                            typeof r.hearts === "number"
                              ? `Сердца: ${r.hearts}`
                              : r.items_granted?.length
                                ? "Стикер в альбоме!"
                                : "Куплено",
                          );
                          load();
                        })
                        .catch((err) => setShopMsg(err instanceof Error ? err.message : "Не хватило монет"));
                    }}
                  >
                    <span className="flex w-full items-center justify-between gap-3">
                      <span className="font-[family-name:var(--font-display)] text-base text-[#f5ed75]">{item.title_ru}</span>
                      <span className="inline-flex items-center gap-1.5 text-sm font-extrabold text-[#f5ed75]">
                        <BrandIcon name="coin" className="!h-6 !w-6" />
                        {item.coins}
                      </span>
                    </span>
                  </RoomTile>
                ))}
                {shopMsg ? <p className="text-center text-sm font-bold text-[#ee7349]">{shopMsg}</p> : null}
              </>
            ) : null}

            {room === "glory" ? (
              <>
                <RoomKicker>Башня славы</RoomKicker>
                <RoomTitle>{TIER_RU[league?.tier || "bronze"] || "Лига"}</RoomTitle>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/world/ui/glory-flag.png"
                  alt="Флаг Фоксинбург"
                  className="mx-auto h-28 w-auto object-contain drop-shadow-lg sm:h-36"
                />
                <RoomTile icon={<BrandIcon name="xp" />} label="XP за неделю" value={league?.weekly_xp ?? 0} />
                <RoomTile
                  icon={<BrandIcon name="star" />}
                  label="Место"
                  value={`${league?.rank ?? 1} / ${league?.size ?? 1}`}
                />
                <RoomTile icon={<BrandIcon name="xp" />} label="Всего XP" value={player?.xp ?? 0} />
                <RoomTile label="Стикеры" value={stickerOwned} />
                {league?.top?.length ? (
                  <div className="mx-auto w-full max-w-[min(92vw,22rem)] space-y-2">
                    {league.top.map((row) => (
                      <RoomTile
                        key={`${row.rank}-${row.display_name}`}
                        highlight={Boolean(row.is_me)}
                        label={`${row.rank}. ${row.display_name}`}
                        value={`${row.weekly_xp} XP`}
                      />
                    ))}
                  </div>
                ) : null}
              </>
            ) : null}

            {room === "lexicon" ? (
              <>
                <RoomKicker>Сокровищница слов</RoomKicker>
                <RoomTitle>Слова, что уже звучали</RoomTitle>
                <RoomLead>
                  Выучено {learned.length}
                  {dueCount > 0 ? ` · пора повторить ${dueCount}` : " · всё свежее"}
                </RoomLead>
                {dueCount > 0 ? (
                  <RoomCta href="/learn/practice" tone="teal">
                    Повторить {dueCount} {dueCount === 1 ? "слово" : "слов"}
                  </RoomCta>
                ) : null}
                <ul className="mx-auto grid max-w-lg grid-cols-2 gap-2 sm:grid-cols-3">
                  {showWords.map((w) => (
                    <li key={`${w.unit}-${w.en}`}>
                      <RoomRelic active={due.has(w.en)}>
                        {w.image ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={w.image} alt={w.en} className="mx-auto h-12 w-12 object-contain" loading="lazy" />
                        ) : null}
                        <p className="mt-0.5 font-[family-name:var(--font-display)] text-base font-extrabold text-[#f5ed75]">
                          {w.en}
                        </p>
                        {w.ipa ? <p className="text-[10px] font-bold text-[#7fd8c9]/80">{w.ipa}</p> : null}
                      </RoomRelic>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {room === "stickers" ? (
              <>
                <RoomKicker>Башня стикеров</RoomKicker>
                <RoomTitle>Альбом замка</RoomTitle>
                <StickerPreviewRow stickers={stickers} />
                <StickerCollection stickers={stickers} ownedCount={stickerOwned} />
              </>
            ) : null}

            {room === "nest" ? (
              <>
                <RoomKicker>Гнездо Foxy</RoomKicker>
                <RoomTitle>{player?.display_name || "Исследователь"}</RoomTitle>
                <RoomTile
                  icon={<BrandIcon name="star" />}
                  label="Уровень"
                  value={`${player?.level_title_ru || player?.level_title} · ${player?.level}`}
                />
                <RoomTile icon={<BrandIcon name="streak" />} label="Серия дней" value={player?.streak_days ?? 0} />
                <RoomTile icon={<BrandIcon name="heart" />} label="Сердца" value={hearts} />
              </>
            ) : null}

            {room === "quests" ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/world/ui/frames/quest-plaque.png"
                  alt=""
                  className="mx-auto mb-1 h-14 w-auto max-w-[min(92vw,18rem)] object-contain drop-shadow-lg"
                />
                <RoomKicker>Беседка поручений</RoomKicker>
                <RoomTitle>Задания дня</RoomTitle>
                {quests.map((q) => (
                  <RoomTile
                    key={q.id || q.title_ru}
                    highlight={Boolean(q.claimable || q.claimed)}
                    label={`${q.done ? "✓ " : ""}${q.title_ru}`}
                    value={
                      q.claimed ? "Получено" : q.claimable ? "Забрать" : `${q.progress}/${q.target}`
                    }
                    onClick={
                      q.claimable && q.id
                        ? () => {
                            void worldApi
                              .claimDailyQuest(q.id!)
                              .then((r) => {
                                setQuestMsg(r.xp_delta ? `+${r.xp_delta} XP` : "Уже получено");
                                load();
                              })
                              .catch(() => load());
                          }
                        : undefined
                    }
                  />
                ))}
                {questMsg ? <p className="text-center text-sm font-bold text-[#f5ed75]">{questMsg}</p> : null}
                <RoomCta href="/learn">Выполнить поручение</RoomCta>
              </>
            ) : null}

            {room === "yard" ? (
              <>
                <RoomKicker>Двор тренировки</RoomKicker>
                <RoomTitle>Поле смелости</RoomTitle>
                <RoomCta href="/learn/practice">{dueCount > 0 ? `Повторить ${dueCount}` : "Тренировка"}</RoomCta>
                <RoomCta href="/lesson/practice" tone="teal">
                  Игра на скорость
                </RoomCta>
                <RoomCta href="/learn" tone="ghost">
                  Открыть текущий урок
                </RoomCta>
              </>
            ) : null}
          </RoomSheet>
        </div>
      ) : null}
    </main>
  );
}

function HudChip({
  icon,
  value,
  gold = false,
}: {
  icon: React.ReactNode;
  value: React.ReactNode;
  gold?: boolean;
}) {
  return <FantasyHudChip icon={icon} value={value} gold={gold} />;
}
