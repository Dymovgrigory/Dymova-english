"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { SPOTS, TIER_RU, type Spot, type SpotId } from "@/castle/buildings";
import { CastleStage } from "@/features/castle/CastleStage";
import { FittingRoom } from "@/features/castle/FittingRoom";
import { Workshop } from "@/features/castle/Workshop";
import { Button } from "@/design/Button";
import { ContentImage } from "@/design/ContentImage";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { Shell } from "@/design/Shell";
import { StatPill } from "@/design/StatPill";
import { humanizeError, worldApi, type League, type Player } from "@/lib/api";
import { isProfileMissing, isUnauthorized, v2 } from "@/lib/v2/client";
import { castleApi, type CastleView, type LexiconChestOpen, type LexiconChestStatus } from "@/lib/v2/castle";
import type { Courses, Home, PracticeStatus, Quest, QuestBoard, WordsBook } from "@/lib/v2/types";
import { formatWeekRange, medalForRank } from "@/lib/v2/weeks";
import { stickerArt } from "@/ui/fantasy/StickerDrawer";

type ShopItem = { sku: string; coins: number; title_ru: string };
type Sticker = { id: string; title_ru: string; emoji: string; owned: boolean };

type CastleData = {
  home: Home;
  courses: Courses;
  words: WordsBook | null;
  player: Player | null;
  hearts: number;
  shop: ShopItem[];
  questBoard: QuestBoard | null;
  chest: LexiconChestStatus | null;
  trial: PracticeStatus | null;
  stickers: Sticker[];
  stickerOwned: number;
  league: League | null;
  dueCount: number;
};


/** Лавка: припасы (сердца, заморозка) и Мастерская облика — единственный выход монетам. */
function ShopRoom({
  shop,
  castle,
  shopMsg,
  onBuy,
  onCastleChange,
  onFit,
}: {
  shop: ShopItem[];
  castle: CastleView | null;
  shopMsg: string | null;
  onBuy: (sku: string) => void;
  onCastleChange: (view: CastleView) => void;
  onFit: () => void;
}) {
  const [tab, setTab] = useState<"supplies" | "workshop">("supplies");
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-1 rounded-2xl bg-[#3b2a1e]/10 p-1" role="tablist">
        {(
          [
            ["supplies", "Припасы"],
            ["workshop", "Мастерская облика"],
          ] as const
        ).map(([id, title]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-xl px-3 py-2 text-[14px] font-extrabold ${tab === id ? "mat-brass" : "text-ink-soft"}`}
          >
            {title}
          </button>
        ))}
      </div>
      {tab === "supplies" ? (
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
      ) : castle ? (
        <div className="space-y-3">
          <Button block variant="crown" onClick={onFit}>
            Примерить на замке
          </Button>
          <Workshop view={castle} onChange={onCastleChange} />
        </div>
      ) : (
        <p className="text-center text-[15px] font-semibold text-ink-soft">Витрина не загрузилась. Закрой и открой Лавку ещё раз.</p>
      )}
    </div>
  );
}

/** Наклейка альбома: при битой картинке (404/нет файла) — emoji вместо сломанного img. */
function AlbumSticker({ id, emoji }: { id: string; emoji?: string }) {
  const [broken, setBroken] = useState(false);
  const art = broken ? null : stickerArt(id);
  if (art) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={art} alt="" onError={() => setBroken(true)} className="mx-auto h-14 w-14 object-contain" />
    );
  }
  return (
    <span className="mx-auto grid h-14 w-14 place-items-center font-fairy text-[28px] font-black text-[#3b2a1e]/45">
      {emoji || "★"}
    </span>
  );
}

function RoomPanel({
  spot,
  data,
  castle,
  shopMsg,
  questMsg,
  chestPrize,
  onBuy,
  onClaim,
  onClose,
  onGo,
  onOpenBook,
  onCastleChange,
  onFit,
  onOpenChest,
}: {
  spot: Spot;
  data: CastleData;
  castle: CastleView | null;
  shopMsg: string | null;
  questMsg: string | null;
  chestPrize: LexiconChestOpen | null;
  onBuy: (sku: string) => void;
  onClaim: (quest: Quest) => void;
  onClose: () => void;
  onGo: (href: string) => void;
  onOpenBook: (bookId: string) => void;
  onCastleChange: (view: CastleView) => void;
  onFit: () => void;
  onOpenChest: () => void;
}) {
  const { home, words, player, hearts, shop, questBoard, chest, trial, stickers, stickerOwned, league, dueCount } = data;
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
              <div className="mat-enamel rounded-2xl px-4 py-3">
                <p className="text-[17px] font-extrabold text-ink">Испытание дня</p>
                <p className="mt-0.5 text-[13px] font-bold text-ink-soft">5 слов · 15 секунд на ответ · с первой попытки</p>
                {trial?.trial_done_today ? (
                  <p className="mt-2 text-[15px] font-extrabold text-[#1f6f60]">Пройдено сегодня ✓</p>
                ) : trial && !trial.trial_available ? (
                  <p className="mt-2 text-[15px] font-semibold text-ink-soft">Сначала выучи слова на уроках</p>
                ) : (
                  <Button block className="mt-2" onClick={() => onGo("/lesson/trial")}>
                    Начать испытание
                  </Button>
                )}
              </div>
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
              <div className="mat-enamel rounded-2xl px-4 py-3 text-center">
                <p className="text-[17px] font-extrabold text-ink">Сундук слов</p>
                {chestPrize ? (
                  <div className="mt-2 flex flex-col items-center gap-1">
                    <p className="text-[16px] font-extrabold text-[#d69e00]">+{chestPrize.coins} монет</p>
                    {chestPrize.item_id ? (
                      <>
                        <ContentImage
                          path={`/content/castle/decor/${chestPrize.item_id}.webp`}
                          alt={castle?.catalog.find((i) => i.id === chestPrize.item_id)?.title_ru ?? "Украшение"}
                          className="h-20 w-20"
                          fallback="★"
                        />
                        <p className="text-[14px] font-extrabold text-ink">
                          {castle?.catalog.find((i) => i.id === chestPrize.item_id)?.title_ru ?? "Украшение для замка"}
                        </p>
                      </>
                    ) : null}
                  </div>
                ) : chest && chest.ready > 0 ? (
                  <Button block variant="crown" className="mt-2" onClick={onOpenChest}>
                    Открыть сундук
                  </Button>
                ) : (
                  <p className="mt-1 text-[14px] font-bold text-ink-soft">
                    Слов до сундука: {chest?.progress ?? 0}/{chest?.per_chest ?? 25}
                  </p>
                )}
              </div>
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
            <ShopRoom shop={shop} castle={castle} shopMsg={shopMsg} onBuy={onBuy} onCastleChange={onCastleChange} onFit={onFit} />
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
                        {row.is_me && castle?.titles.find((t) => t.worn)?.title_ru ? (
                          <span className="block text-[11px] font-bold text-ink-soft">
                            {castle.titles.find((t) => t.worn)?.title_ru}
                          </span>
                        ) : null}
                      </span>
                      <span>{row.weekly_xp} XP</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[15px] font-semibold text-ink-soft">Пройди урок — появишься в лиге.</p>
              )}
              <div className="space-y-1.5">
                <h3 className="text-[15px] font-extrabold text-ink">Трофеи</h3>
                {league?.history?.length ? (
                  <ul className="space-y-1.5">
                    {league.history.map((row) => (
                      <li
                        key={row.week_start}
                        className="mat-enamel flex items-center justify-between gap-2 rounded-2xl px-3 py-2 text-[14px] font-bold text-ink"
                      >
                        <span>
                          {medalForRank(row.rank) ? `${medalForRank(row.rank)} ` : ""}
                          {row.rank} место · {formatWeekRange(row.week_start)}
                        </span>
                        <span className="text-ink-soft">
                          {row.weekly_xp} XP · <span className="text-[#d69e00]">+{row.coins_awarded} монет</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[14px] font-semibold text-ink-soft">Закрой неделю в лиге, и трофей появится здесь.</p>
                )}
              </div>
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
                  {stickers.map((sticker) => (
                    <li
                      key={sticker.id}
                      className={[
                        "rounded-2xl px-1.5 py-2 text-center",
                        sticker.owned ? "mat-enamel" : "bg-[#3b2a1e]/10 ring-1 ring-[#3b2a1e]/15",
                      ].join(" ")}
                    >
                        {/* Не полученная наклейка — сюрприз: только знак вопроса; битая картинка — emoji */}
                        {sticker.owned ? (
                          <AlbumSticker id={sticker.id} emoji={sticker.emoji} />
                        ) : (
                          <span className="mx-auto grid h-14 w-14 place-items-center font-fairy text-[28px] font-black text-[#3b2a1e]/45">
                            ?
                          </span>
                        )}
                        <p className={`mt-1 text-[11px] font-extrabold leading-tight ${sticker.owned ? "text-ink" : "text-ink-soft"}`}>
                          {sticker.title_ru}
                        </p>
                    </li>
                  ))}
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
              {castle ? (
                <div className="space-y-2">
                  <h3 className="text-[15px] font-extrabold text-ink">Звания</h3>
                  <ul className="space-y-1.5">
                    {castle.titles.map((row) => (
                      <li key={row.track} className="mat-enamel flex items-center justify-between gap-2 rounded-2xl px-3 py-2">
                        <span className="min-w-0">
                          <span className="block truncate text-[15px] font-extrabold text-ink">
                            {row.title_ru ?? row.track_title_ru}
                          </span>
                          <span className="block text-[12px] font-bold text-ink-soft">
                            {row.value} {row.unit_ru}
                            {row.next_threshold ? ` · до следующего ${row.next_threshold - row.value}` : " · максимум"}
                          </span>
                        </span>
                        <button
                          type="button"
                          disabled={row.level === 0 || row.worn}
                          onClick={() => void castleApi.wear(row.track).then(onCastleChange)}
                          className="shrink-0 rounded-xl px-3 py-1.5 text-[13px] font-extrabold text-ink ring-1 ring-[#3b2a1e]/25 disabled:opacity-45"
                        >
                          {row.worn ? "Надето" : "Носить"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <Button block variant="paper" onClick={() => onGo("/profile")}>
                Профиль ученика
              </Button>
            </div>
          )}

          {room === "quests" && (
            <div className="space-y-4">
              {(
                [
                  ["Сегодня", questBoard?.daily ?? []],
                  ["Эта неделя", questBoard?.weekly ?? []],
                ] as const
              ).map(([section, list]) => (
                <section key={section} className="space-y-2">
                  <h3 className="text-[15px] font-extrabold text-ink">{section}</h3>
                  {list.length === 0 ? (
                    <p className="text-[14px] font-semibold text-ink-soft">Задания появятся после первого урока.</p>
                  ) : (
                    <ul className="space-y-2">
                      {list.map((q) => (
                        <li key={q.id} className="mat-enamel flex items-center justify-between gap-3 rounded-2xl px-4 py-3">
                          <div className="min-w-0">
                            <p className="text-[15px] font-extrabold text-ink">
                              {q.done ? "✓ " : ""}
                              {q.title_ru}
                            </p>
                            <p className="text-[13px] font-bold text-ink-soft">
                              {q.progress}/{q.target} · <span className="text-[#d69e00]">+{q.coins} монет</span>
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {q.claimed ? (
                              <span className="text-[13px] font-extrabold text-[#1f6f60]">Получено</span>
                            ) : q.claimable ? (
                              <button
                                type="button"
                                onClick={() => onClaim(q)}
                                className="mat-brass rounded-xl px-3 py-1.5 text-[13px] font-extrabold"
                              >
                                Забрать
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => onGo(q.href)}
                                aria-label={`Перейти: ${q.title_ru}`}
                                className="rounded-xl px-3 py-1.5 text-[13px] font-extrabold text-ink ring-1 ring-[#3b2a1e]/25"
                              >
                                Перейти
                              </button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}
              {questMsg ? <p className="text-center text-[15px] font-bold text-[#1f6f60]">{questMsg}</p> : null}
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
  const [castle, setCastle] = useState<CastleView | null>(null);
  const [fitting, setFitting] = useState(false);
  const [chestPrize, setChestPrize] = useState<LexiconChestOpen | null>(null);

  const load = () => {
    void worldApi
      .ensurePlayer(typeof window !== "undefined" ? window.localStorage.getItem("world.name") || "Исследователь" : "Исследователь")
      .then(() => Promise.all([v2.home(), v2.courses()]))
      .then(async ([home, courses]) => {
        const [words, learnHome, shopBody, league, review, castleBody, questBoard, chest, trial] = await Promise.all([
          v2.words(home.profile.book_id).catch(() => null),
          worldApi.getLearnHome().catch(() => null),
          worldApi.getShop().catch(() => ({ items: [] as ShopItem[] })),
          worldApi.getLeague().catch(() => null),
          worldApi.getReview().catch(() => null),
          castleApi.get().catch(() => null),
          v2.quests().catch(() => null),
          castleApi.lexiconChestStatus().catch(() => null),
          v2.practiceStatus().catch(() => null),
        ]);
        setError(null);
        setNeedsSetup(false);
        if (castleBody) setCastle(castleBody);
        setData({
          home,
          courses,
          words,
          player: learnHome?.player ?? null,
          hearts: learnHome?.hearts?.current ?? 5,
          shop: shopBody.items,
          questBoard,
          chest,
          trial,
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
  const claimable = useMemo(
    () => (data?.questBoard ? [...data.questBoard.daily, ...data.questBoard.weekly].filter((q) => q.claimable).length : 0),
    [data],
  );
  const openSpot = SPOTS.find((s) => s.id === openId) ?? null;

  // Приз сундука и сообщение Беседки живут, пока открыта их комната.
  const openRoom = (id: SpotId | null) => {
    setChestPrize(null);
    setQuestMsg(null);
    setOpenId(id);
  };

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
        appearance={castle?.appearance ?? null}
        decor={castle?.decor ?? []}
        emblem={castle?.titles.find((t) => t.worn)?.track ?? "fox"}
        onOpen={openRoom}
      />
      {fitting && castle ? (
        <FittingRoom view={castle} onChange={setCastle} onClose={() => setFitting(false)} />
      ) : null}

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
                  onClick={() => openRoom(spot.id)}
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
          castle={castle}
          shopMsg={shopMsg}
          questMsg={questMsg}
          chestPrize={chestPrize}
          onCastleChange={setCastle}
          onFit={() => setFitting(true)}
          onClose={() => openRoom(null)}
          onGo={(href) => router.push(href)}
          onOpenBook={(bookId) => void openBook(bookId)}
          onOpenChest={() => {
            void castleApi
              .lexiconChestOpen()
              .then((prize) => {
                setChestPrize(prize);
                load();
              })
              .catch(() => load());
          }}
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
              .catch((err) => setShopMsg(humanizeError(err, "Не хватило монет")));
          }}
          onClaim={(quest) => {
            void v2
              .claimQuest(quest.id, quest.period)
              .then((r) => {
                setQuestMsg(`+${r.coins_delta} монет`);
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
