"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  CASTLE_FOCUS,
  CASTLE_HOTSPOTS,
  CASTLE_LABEL_STEP,
  CASTLE_SCENE,
  CASTLE_SCENE_SIZE,
  SPOTS,
  TIER_RU,
  spotAt,
  type HotspotMap,
  type Spot,
  type SpotId,
} from "@/castle/buildings";
import { fitScene } from "@/castle/scene";
import { Button } from "@/design/Button";
import { ContentImage } from "@/design/ContentImage";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { Shell } from "@/design/Shell";
import { StatPill } from "@/design/StatPill";
import { worldApi, type League, type Player } from "@/lib/api";
import { isProfileMissing, isUnauthorized, v2 } from "@/lib/v2/client";
import type { Courses, Home, WordsBook } from "@/lib/v2/types";
import { stickerArt } from "@/ui/fantasy/StickerDrawer";

type ShopItem = { sku: string; coins: number; title_ru: string };
type Quest = { id?: string; title_ru: string; progress: number; target: number; done: boolean; claimed?: boolean; claimable?: boolean };
type Sticker = { id: string; title_ru: string; emoji: string; owned: boolean };

type CastleData = {
  home: Home;
  courses: Courses;
  words: WordsBook | null;
  player: Player | null;
  hearts: number;
  shop: ShopItem[];
  quests: Quest[];
  stickers: Sticker[];
  stickerOwned: number;
  league: League | null;
  dueCount: number;
};

/** Карта зон из PNG: номер здания на пиксель. Пока не загрузилась — работают кнопки-области. */
function useHotspotMap(): HotspotMap | null {
  const [map, setMap] = useState<HotspotMap | null>(null);
  useEffect(() => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return;
      context.drawImage(image, 0, 0);
      const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
      const labels = new Uint8Array(canvas.width * canvas.height);
      for (let i = 0; i < labels.length; i += 1) labels[i] = Math.round(data[i * 4] / CASTLE_LABEL_STEP);
      setMap({ width: canvas.width, height: canvas.height, labels });
    };
    image.src = CASTLE_HOTSPOTS;
  }, []);
  return map;
}

/** Подсветка здания: вырез той же диорамы по маске силуэта — на месте, только свечение и подпись. */
function SpotHighlight({ spot, active, pulse }: { spot: Spot; active: boolean; pulse: boolean }) {
  const { left, top, width, height } = spot.area;
  const shown = active || pulse;
  return (
    <div
      aria-hidden
      className={[
        "pointer-events-none absolute transition-opacity duration-200 ease-out motion-reduce:transition-none",
        pulse ? "castle-pulse" : "",
      ].join(" ")}
      style={{
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
        zIndex: 10 + spot.index,
        opacity: shown ? 1 : 0,
        filter: "drop-shadow(0 0 6px rgb(255 211 110 / 0.9)) drop-shadow(0 10px 12px rgb(20 10 30 / 0.45))",
      }}
    >
      <div
        className="h-full w-full"
        style={{
          backgroundImage: `url(${CASTLE_SCENE})`,
          backgroundSize: `${10000 / width}% ${10000 / height}%`,
          backgroundPosition: `${(left / (100 - width)) * 100}% ${(top / (100 - height)) * 100}%`,
          WebkitMaskImage: `url(${spot.mask})`,
          maskImage: `url(${spot.mask})`,
          WebkitMaskSize: "100% 100%",
          maskSize: "100% 100%",
          filter: "brightness(1.14) saturate(1.06)",
        }}
      />
      <span
        className="mat-brass absolute left-1/2 -translate-x-1/2 -translate-y-[calc(100%+4px)] whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-extrabold leading-none shadow-lg lg:text-[13px]"
        style={{ top: `${spot.labelTop}%` }}
      >
        {spot.title}
      </span>
    </div>
  );
}

/** Где на экране лежит диорама: замок вписан в свободную область `freeArea`, пейзаж — на весь экран. */
function useSceneFit(freeArea: HTMLElement | null) {
  const [fit, setFit] = useState<{ scale: number; left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const update = () => {
      const free = freeArea?.getBoundingClientRect();
      if (!free) return;
      setFit(
        fitScene(
          { width: window.innerWidth, height: window.innerHeight },
          { left: free.left, top: free.top, width: free.width, height: free.height },
          CASTLE_SCENE_SIZE,
          CASTLE_FOCUS,
        ),
      );
    };
    update();
    const observer = new ResizeObserver(update);
    if (freeArea) observer.observe(freeArea);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [freeArea]);
  return fit;
}

/** Если диорама не закрывает экран по высоте — края растворяются в размытой подложке, без резкой границы. */
const EDGE_FADE = "linear-gradient(to bottom, transparent, #000 12%, #000 88%, transparent)";

/** Сцена замка на весь экран: одна картинка, здание под курсором/пальцем — по карте зон. */
function CastleStage({
  freeArea,
  openId,
  pulsing,
  onOpen,
}: {
  freeArea: HTMLElement | null;
  openId: SpotId | null;
  pulsing: SpotId[];
  onOpen: (id: SpotId) => void;
}) {
  const map = useHotspotMap();
  const fit = useSceneFit(freeArea);
  const sceneRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<SpotId | null>(null);
  const [focused, setFocused] = useState<SpotId | null>(null);

  const covers =
    !!fit &&
    typeof window !== "undefined" &&
    fit.top <= 0 &&
    fit.top + CASTLE_SCENE_SIZE.height * fit.scale >= window.innerHeight;

  const pointAt = (clientX: number, clientY: number): SpotId | null => {
    const rect = sceneRef.current?.getBoundingClientRect();
    if (!map || !rect) return null;
    return spotAt(map, (clientX - rect.left) / rect.width, (clientY - rect.top) / rect.height);
  };

  return (
    <div className="fixed inset-0 z-0 overflow-hidden bg-[#1a1230]">
      {/* Подложка на случай узкого экрана, где картинка не закрывает всё */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={CASTLE_SCENE} alt="" aria-hidden className="absolute inset-0 h-full w-full scale-110 object-cover blur-2xl" />
      {fit ? (
        <div
          ref={sceneRef}
          className="absolute touch-manipulation select-none"
          style={{
            left: fit.left,
            top: fit.top,
            width: CASTLE_SCENE_SIZE.width * fit.scale,
            height: CASTLE_SCENE_SIZE.height * fit.scale,
            cursor: hovered ? "pointer" : "default",
          }}
          onPointerMove={(event) => {
            if (event.pointerType === "mouse") setHovered(pointAt(event.clientX, event.clientY));
          }}
          onPointerLeave={() => setHovered(null)}
          onClick={(event) => {
            const id = pointAt(event.clientX, event.clientY);
            if (id) onOpen(id);
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={CASTLE_SCENE}
            alt="Замок Фоксинбург"
            draggable={false}
            className="absolute inset-0 h-full w-full"
            style={covers ? undefined : { WebkitMaskImage: EDGE_FADE, maskImage: EDGE_FADE }}
          />
          {SPOTS.map((spot) => (
            <SpotHighlight
              key={spot.id}
              spot={spot}
              active={hovered === spot.id || focused === spot.id || openId === spot.id}
              pulse={pulsing.includes(spot.id)}
            />
          ))}
          {/* Клавиатура и скринридеры: кнопки по областям зданий, мышь их не перехватывает. */}
          {SPOTS.map((spot) => (
            <button
              key={spot.id}
              type="button"
              aria-label={`${spot.title} — ${spot.hint}`}
              data-spot={spot.id}
              className="pointer-events-none absolute rounded-xl opacity-0 focus-visible:outline-none"
              style={{ left: `${spot.area.left}%`, top: `${spot.area.top}%`, width: `${spot.area.width}%`, height: `${spot.area.height}%` }}
              onFocus={() => setFocused(spot.id)}
              onBlur={() => setFocused(null)}
              onClick={(event) => {
                event.stopPropagation();
                onOpen(spot.id);
              }}
            />
          ))}
        </div>
      ) : null}
      {/* Мягкое затемнение краёв под заголовком и лентой */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{ background: "linear-gradient(to bottom, rgb(26 18 48 / 0.55), transparent 22%, transparent 72%, rgb(26 18 48 / 0.6))" }}
      />
    </div>
  );
}

function RoomPanel({
  spot,
  data,
  shopMsg,
  questMsg,
  onBuy,
  onClaim,
  onClose,
  onGo,
  onOpenBook,
}: {
  spot: Spot;
  data: CastleData;
  shopMsg: string | null;
  questMsg: string | null;
  onBuy: (sku: string) => void;
  onClaim: (id: string) => void;
  onClose: () => void;
  onGo: (href: string) => void;
  onOpenBook: (bookId: string) => void;
}) {
  const { home, words, player, hearts, shop, quests, stickers, stickerOwned, league, dueCount } = data;
  const room = spot.id;
  const wordRows = (words?.modules ?? []).flatMap((m) => m.words.map((w) => ({ ...w, module: m.title_ru })));
  const learned = wordRows.filter((w) => w.strength > 0);
  const showWords = (learned.length ? learned : wordRows).slice(0, 24);
  const studyLabel = home.current_node?.module_title_ru ?? "твой класс";

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#241a30]" role="dialog" aria-modal="true" aria-label={spot.title}>
      <div className="absolute inset-0">
        {spot.room ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={spot.room} alt="" className="h-full w-full object-cover object-center" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={spot.art} alt="" className="h-full w-full bg-[#1a1230] object-contain object-center px-10 pb-40 pt-28" />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-[#241a30]/70 via-transparent via-30% to-[#241a30]/55" />
      </div>

      <header className="relative z-10 flex items-start justify-between gap-3 px-4 pb-2 pt-[max(1rem,env(safe-area-inset-top))]">
        <div>
          <p className="text-[12px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">Замок Фоксинбург</p>
          <h2 className="font-fairy text-[32px] font-black leading-tight text-[#ffd36e]">{spot.title}</h2>
          <p className="mt-1 text-[15px] font-semibold text-[#c9bfd8]">{spot.hint}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="mat-enamel flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-[22px] font-black text-ink"
          aria-label="Закрыть"
        >
          ×
        </button>
      </header>

      {/* Плашка внизу: интерьер в центре остаётся открытым и просвечивает сквозь пергамент */}
      <div className="relative z-10 mx-auto mt-auto flex w-full max-w-xl flex-col px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <div className="mat-parchment-veil max-h-[52dvh] overflow-y-auto rounded-[28px] px-5 py-4">
          {spot.kind === "tower" && spot.bookId && (
            <div className="flex flex-col items-center gap-4 text-center">
              <Foxy pose="wave" size={84} />
              <p className="text-[20px] font-extrabold text-ink">Башня учебника Spotlight {spot.bookId.replace("sp", "")}</p>
              <p className="text-[15px] font-semibold text-ink-soft">Здесь начинается путь {spot.bookId.replace("sp", "")} класса.</p>
              <Button block onClick={() => onOpenBook(spot.bookId!)}>
                Открыть путь класса
              </Button>
            </div>
          )}

          {room === "school" && (
            <div className="flex flex-col items-center gap-4 text-center">
              <Foxy pose="wave" size={84} />
              <p className="text-[20px] font-extrabold text-ink">Здесь начинается путь по твоему учебнику.</p>
              <p className="text-[15px] font-semibold text-ink-soft">
                Сейчас: {studyLabel} · цель дня {home.today_xp}/{home.daily_goal_xp} XP
              </p>
              <Button block onClick={() => onGo("/learn")}>
                К пути обучения
              </Button>
            </div>
          )}

          {room === "yard" && (
            <div className="flex flex-col gap-3 text-center">
              <Foxy pose="think" size={84} />
              <p className="text-[18px] font-extrabold text-ink">
                {dueCount > 0 ? `Ждут повторения: ${dueCount}` : "Слова свежие — можно потренироваться всё равно"}
              </p>
              <Button block onClick={() => onGo("/practice")}>
                {dueCount > 0 ? `Тренировка · ${dueCount}` : "Открыть тренировку"}
              </Button>
              <Button block variant="paper" onClick={() => onGo("/learn")}>
                Вернуться к пути
              </Button>
            </div>
          )}

          {room === "lexicon" && (
            <div className="space-y-4">
              <p className="text-[17px] font-extrabold text-ink">
                В словаре: {wordRows.length}
                {dueCount > 0 ? ` · пора повторить ${dueCount}` : ""}
              </p>
              {showWords.length === 0 ? (
                <p className="text-[15px] font-semibold text-ink-soft">Пройди урок — слова появятся здесь.</p>
              ) : (
                <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {showWords.map((w) => (
                    <li key={w.id} className="mat-enamel rounded-2xl px-2 py-3 text-center">
                      <ContentImage path={w.image} alt={w.en} className="mx-auto h-14 w-14" fallback={w.en.slice(0, 2)} />
                      <p className="mt-1 font-fairy text-[16px] font-black text-[#4a2a66]">{w.en}</p>
                      <p className="text-[12px] font-bold text-ink-soft">{w.ru}</p>
                    </li>
                  ))}
                </ul>
              )}
              <Button block variant="mint" onClick={() => onGo("/words")}>
                Открыть словарь
              </Button>
            </div>
          )}

          {room === "shop" && (
            <div className="space-y-3">
              <p className="text-[15px] font-semibold text-ink-soft">Монеты зарабатываются уроками и сундуками на пути.</p>
              <ul className="space-y-2">
                {shop.map((item) => (
                  <li key={item.sku}>
                    <button
                      type="button"
                      onClick={() => onBuy(item.sku)}
                      className="mat-enamel flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left"
                    >
                      <span className="font-fairy text-[17px] font-black text-[#4a2a66]">{item.title_ru}</span>
                      <span className="inline-flex items-center gap-1 text-[16px] font-extrabold text-[#d69e00]">
                        <Icon name="coin" size={18} />
                        {item.coins}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {shopMsg ? <p className="text-center text-[15px] font-bold text-[#a82f25]">{shopMsg}</p> : null}
            </div>
          )}

          {room === "glory" && (
            <div className="space-y-3">
              <p className="font-fairy text-[22px] font-black text-[#4a2a66]">{TIER_RU[league?.tier || "bronze"] || "Лига"}</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="mat-enamel rounded-2xl px-3 py-3 text-center">
                  <p className="text-[12px] font-bold text-ink-soft">Место</p>
                  <p className="text-[22px] font-extrabold text-ink">
                    {league?.rank ?? "—"} / {league?.size ?? "—"}
                  </p>
                </div>
                <div className="mat-enamel rounded-2xl px-3 py-3 text-center">
                  <p className="text-[12px] font-bold text-ink-soft">XP недели</p>
                  <p className="text-[22px] font-extrabold text-ink">{league?.weekly_xp ?? 0}</p>
                </div>
              </div>
              {league?.top?.length ? (
                <ul className="space-y-1.5">
                  {league.top.slice(0, 5).map((row) => (
                    <li
                      key={`${row.rank}-${row.display_name}`}
                      className={`flex justify-between rounded-xl px-3 py-2 text-[14px] font-bold ${
                        row.is_me ? "bg-[#ffd36e]/35 text-ink" : "bg-black/5 text-ink-soft"
                      }`}
                    >
                      <span>
                        {row.rank}. {row.display_name}
                      </span>
                      <span>{row.weekly_xp} XP</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[15px] font-semibold text-ink-soft">Пройди урок — появишься в лиге.</p>
              )}
            </div>
          )}

          {room === "stickers" && (
            <div className="space-y-3">
              <p className="text-[17px] font-extrabold text-ink">
                В альбоме: {stickerOwned} из {stickers.length}
              </p>
              {stickers.length === 0 ? (
                <p className="text-[15px] font-semibold text-ink-soft">Проходи уроки — наклейки появятся здесь.</p>
              ) : (
                <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                  {stickers.map((sticker) => {
                    const art = stickerArt(sticker.id);
                    return (
                      <li
                        key={sticker.id}
                        className={[
                          "rounded-2xl px-1.5 py-2 text-center",
                          sticker.owned ? "mat-enamel" : "bg-[#3b2a1e]/10 ring-1 ring-[#3b2a1e]/15",
                        ].join(" ")}
                      >
                        {/* Не полученная наклейка — сюрприз: только знак вопроса */}
                        {sticker.owned && art ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={art} alt="" className="mx-auto h-14 w-14 object-contain" />
                        ) : (
                          <span className="mx-auto grid h-14 w-14 place-items-center font-fairy text-[28px] font-black text-[#3b2a1e]/45">
                            {sticker.owned ? sticker.emoji || "★" : "?"}
                          </span>
                        )}
                        <p className={`mt-1 text-[11px] font-extrabold leading-tight ${sticker.owned ? "text-ink" : "text-ink-soft"}`}>
                          {sticker.title_ru}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
              <Button block variant="paper" onClick={() => onGo("/learn")}>
                К урокам за новыми наклейками
              </Button>
            </div>
          )}

          {room === "nest" && (
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <Foxy pose="cheer" size={84} />
                <div>
                  <p className="font-fairy text-[24px] font-black text-[#4a2a66]">
                    {player?.display_name || home.player.display_name}
                  </p>
                  <p className="text-[15px] font-semibold text-ink-soft">
                    Уровень {player?.level ?? home.player.level} · серия {home.streak_days} дн.
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="mat-enamel rounded-2xl px-2 py-3 text-center">
                  <Icon name="bolt" size={22} className="mx-auto text-[#b7791f]" filled />
                  <p className="mt-1 text-[20px] font-extrabold tabular-nums text-ink">{home.player.xp}</p>
                  <p className="text-[11px] font-bold text-ink-soft">XP</p>
                </div>
                <div className="mat-enamel rounded-2xl px-2 py-3 text-center">
                  <Icon name="coin" size={22} className="mx-auto text-[#d69e00]" />
                  <p className="mt-1 text-[20px] font-extrabold tabular-nums text-ink">{home.player.coins}</p>
                  <p className="text-[11px] font-bold text-ink-soft">монеты</p>
                </div>
                <div className="mat-enamel rounded-2xl px-2 py-3 text-center">
                  <Icon name="flame" size={22} className="mx-auto text-[#ff8a3d]" filled />
                  <p className="mt-1 text-[20px] font-extrabold tabular-nums text-ink">{hearts}</p>
                  <p className="text-[11px] font-bold text-ink-soft">сердца</p>
                </div>
              </div>
              <Button block variant="paper" onClick={() => onGo("/profile")}>
                Профиль ученика
              </Button>
            </div>
          )}

          {room === "quests" && (
            <div className="space-y-3">
              {quests.length === 0 ? (
                <p className="text-[15px] font-semibold text-ink-soft">Поручения появятся после первого урока.</p>
              ) : (
                quests.map((q) => (
                  <button
                    key={q.id || q.title_ru}
                    type="button"
                    disabled={!q.claimable || !q.id}
                    onClick={() => q.id && onClaim(q.id)}
                    className="mat-enamel flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left disabled:opacity-70"
                  >
                    <span className="text-[15px] font-extrabold text-ink">
                      {q.done ? "✓ " : ""}
                      {q.title_ru}
                    </span>
                    <span className="text-[13px] font-bold text-ink-soft">
                      {q.claimed ? "Получено" : q.claimable ? "Забрать" : `${q.progress}/${q.target}`}
                    </span>
                  </button>
                ))
              )}
              {questMsg ? <p className="text-center text-[15px] font-bold text-[#1f6f60]">{questMsg}</p> : null}
              <Button block onClick={() => onGo("/learn")}>
                К урокам
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function CastleScreen() {
  const router = useRouter();
  const [data, setData] = useState<CastleData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [openId, setOpenId] = useState<SpotId | null>(null);
  const [pulse, setPulse] = useState<SpotId | null>(null);
  const [shopMsg, setShopMsg] = useState<string | null>(null);
  const [questMsg, setQuestMsg] = useState<string | null>(null);

  const load = () => {
    void worldApi
      .ensurePlayer(typeof window !== "undefined" ? window.localStorage.getItem("world.name") || "Исследователь" : "Исследователь")
      .then(() => Promise.all([v2.home(), v2.courses()]))
      .then(async ([home, courses]) => {
        const [words, learnHome, shopBody, league, review] = await Promise.all([
          v2.words(home.profile.book_id).catch(() => null),
          worldApi.getLearnHome().catch(() => null),
          worldApi.getShop().catch(() => ({ items: [] as ShopItem[] })),
          worldApi.getLeague().catch(() => null),
          worldApi.getReview().catch(() => null),
        ]);
        setError(null);
        setNeedsSetup(false);
        setData({
          home,
          courses,
          words,
          player: learnHome?.player ?? null,
          hearts: learnHome?.hearts?.current ?? 5,
          shop: shopBody.items,
          quests: learnHome?.quests || [],
          stickers: learnHome?.stickers?.items || [],
          stickerOwned: learnHome?.stickers?.owned ?? 0,
          league: league || learnHome?.league || null,
          dueCount: review?.due ?? home.due_count ?? 0,
        });
      })
      .catch((err) => {
        // Замок всё равно показываем: без профиля просим пройти знакомство, не уводим со страницы.
        if (isProfileMissing(err) || isUnauthorized(err)) {
          setNeedsSetup(true);
          setError(null);
          return;
        }
        setError(err instanceof Error ? err.message : "Замок не открылся.");
      });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const q = new URLSearchParams(window.location.search).get("pulse") as SpotId | null;
    if (q && SPOTS.some((s) => s.id === q)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPulse(q);
      setOpenId(q);
      const t = window.setTimeout(() => setPulse(null), 6500);
      return () => window.clearTimeout(t);
    }
  }, []);

  const [freeArea, setFreeArea] = useState<HTMLDivElement | null>(null);
  const claimable = useMemo(() => data?.quests.filter((q) => q.claimable).length ?? 0, [data]);
  const openSpot = SPOTS.find((s) => s.id === openId) ?? null;

  const openBook = async (bookId: string) => {
    if (!data) return;
    const book = data.courses.books.find((b) => b.id === bookId);
    const moduleId = book?.modules[0]?.id;
    if (!moduleId) return;
    await v2.saveProfile({
      book_id: bookId,
      module_id: moduleId,
      daily_goal_xp: data.home.profile.daily_goal_xp,
    });
    router.push("/learn");
  };

  return (
    <Shell>
      <CastleStage
        freeArea={freeArea}
        openId={openId}
        pulsing={[...(pulse ? [pulse] : []), ...(claimable > 0 ? (["quests"] as const) : [])]}
        onOpen={setOpenId}
      />

      {/* Интерфейс поверх сцены; пустая середина пропускает клики к зданиям */}
      <div className="pointer-events-none relative z-10 flex h-[calc(100dvh-6rem)] flex-col lg:h-dvh">
        <header className="pointer-events-auto flex shrink-0 flex-wrap items-start justify-between gap-3 px-4 pt-4 lg:px-8 lg:pt-6">
          <div className="max-w-xl">
            <h1 className="font-fairy text-[28px] font-black leading-tight text-[#ffd36e] drop-shadow-[0_2px_10px_rgb(0_0_0/0.6)] lg:text-[40px]">
              Замок Фоксинбург
            </h1>
            <p className="mt-1 text-[14px] font-bold text-[#f6efe2] drop-shadow-[0_1px_6px_rgb(0_0_0/0.8)] lg:text-[16px]">
              Загляни в здания: рейтинг, стикеры, лавка, словарь и задания дня.
            </p>
          </div>
          {data ? (
            <div className="flex flex-wrap items-center justify-end gap-2 sm:gap-3">
              <StatPill icon="flame" value={data.home.streak_days} label="Серия" />
              <StatPill icon="bolt" value={data.home.player.xp} label="Опыт" />
              <StatPill icon="coin" value={data.home.player.coins} label="Монеты" />
            </div>
          ) : null}
        </header>

        {error ? (
          <p className="pointer-events-auto px-4 text-center text-[15px] font-extrabold text-[#ffb3a6]" role="alert">
            {error}
          </p>
        ) : null}

        {needsSetup ? (
          <div className="glass-dusk pointer-events-auto mx-auto mt-2 flex max-w-xl flex-wrap items-center justify-center gap-3 rounded-2xl px-4 py-2">
            <p className="text-center text-[15px] font-extrabold text-[#f6efe2]">Сначала выбери класс и учебник.</p>
            <Link
              href="/onboarding"
              className="mat-brass inline-flex min-h-11 items-center justify-center rounded-2xl px-5 text-[15px] font-extrabold"
            >
              Начать знакомство
            </Link>
          </div>
        ) : null}

        {/* Свободная область: сюда вписывается замок */}
        <div ref={setFreeArea} className="min-h-0 flex-1" aria-hidden />

        <nav aria-label="Локации замка" className="pointer-events-auto shrink-0 px-3 pb-3 lg:px-8 lg:pb-5">
          <ul className="glass-dusk mx-auto grid max-w-5xl grid-cols-6 gap-1 rounded-2xl p-1.5 ring-1 ring-white/10 lg:grid-cols-12">
            {SPOTS.map((spot) => (
              <li key={spot.id}>
                <button
                  type="button"
                  onClick={() => setOpenId(spot.id)}
                  className={[
                    "flex w-full flex-col items-center gap-0.5 rounded-xl px-0.5 py-1 text-center",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffd36e]/70",
                    openId === spot.id || pulse === spot.id ? "mat-brass" : "text-[#f6efe2] hover:bg-white/10",
                  ].join(" ")}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={spot.art} alt="" className="h-7 w-7 object-contain lg:h-9 lg:w-9" draggable={false} />
                  <span className="text-[10px] font-extrabold leading-tight lg:text-[11px]">{spot.short}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      {openSpot && data ? (
        <RoomPanel
          spot={openSpot}
          data={data}
          shopMsg={shopMsg}
          questMsg={questMsg}
          onClose={() => setOpenId(null)}
          onGo={(href) => router.push(href)}
          onOpenBook={(bookId) => void openBook(bookId)}
          onBuy={(sku) => {
            void worldApi
              .buyShop(sku)
              .then((r) => {
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
          onClaim={(id) => {
            void worldApi
              .claimDailyQuest(id)
              .then((r) => {
                setQuestMsg(r.xp_delta ? `+${r.xp_delta} XP` : "Уже получено");
                load();
              })
              .catch(() => load());
          }}
        />
      ) : null}

      {openSpot && !data && needsSetup ? (
        <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-4 sm:items-center">
          <div className="glass-dusk w-full max-w-md rounded-3xl p-5 text-center ring-1 ring-white/15">
            <p className="font-fairy text-[22px] font-black text-[#ffd36e]">{openSpot.title}</p>
            <p className="mt-2 text-[15px] font-semibold text-[#f6efe2]">
              Чтобы зайти внутрь, сначала выбери класс и учебник.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Link
                href="/onboarding"
                className="mat-brass inline-flex min-h-11 items-center justify-center rounded-2xl px-5 text-[15px] font-extrabold"
              >
                Начать знакомство
              </Link>
              <button
                type="button"
                onClick={() => setOpenId(null)}
                className="inline-flex min-h-11 items-center justify-center rounded-2xl px-5 text-[15px] font-extrabold text-[#f6efe2] ring-1 ring-white/20"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Shell>
  );
}
