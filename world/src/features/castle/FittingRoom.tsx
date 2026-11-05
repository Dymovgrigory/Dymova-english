"use client";

import { useState } from "react";

import { THEME_LOOK } from "@/castle/appearance";
import { CastleStage } from "@/features/castle/CastleStage";
import { ApiError } from "@/lib/api";
import { castleApi, type Appearance, type CastleItem, type CastleView } from "@/lib/v2/castle";

const CATEGORY_TITLES: Record<string, string> = {
  theme: "Темы Мира",
  season: "Сезон",
  time: "Время суток",
  weather: "Погода и эффекты",
};

type Field = "theme" | "season" | "time_of_day" | "weather";

const FIELD_BY_KIND: Record<string, Field> = {
  theme: "theme",
  season: "season",
  time: "time_of_day",
  weather: "weather",
};

/** Один слой облика для POST /appearance: strict TS не даёт собрать объект вычисляемым ключом. */
function fieldPatch(field: Field, value: string): Partial<Appearance> {
  if (field === "theme") return { theme: value };
  if (field === "season") return { season: value };
  if (field === "time_of_day") return { time_of_day: value };
  return { weather: value };
}

const TRACK_TITLES: Record<string, string> = {
  lexicon: "Словесник",
  yard: "Тренер",
  nest: "Хранитель огня",
  glory: "Чемпион",
  stickers: "Собиратель",
};

/** Миниатюра варианта в ленте: картинка сезона, цвет темы или подпись. */
function Thumb({ item }: { item: CastleItem }) {
  if (item.kind === "season") {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`/content/castle/seasons/${item.value}.webp`} alt="" className="h-12 w-16 rounded-lg object-cover" />;
  }
  if (item.kind === "theme") {
    return <span className="block h-12 w-16 rounded-xl border-2 border-white/60" style={{ background: THEME_LOOK[item.value]?.swatch }} />;
  }
  return null;
}

/**
 * Примерка облика: замок на весь экран, лента вариантов внизу, выбор виден сразу.
 * Превью — локальное, сервер не трогаем; «Купить» покупает и применяет на месте.
 */
export function FittingRoom({
  view,
  onChange,
  onClose,
}: {
  view: CastleView;
  onChange: (view: CastleView) => void;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState<Appearance>(view.appearance);
  const [category, setCategory] = useState<string>("theme");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [freeArea, setFreeArea] = useState<HTMLDivElement | null>(null);

  const items = view.catalog.filter((item) => item.kind === category);
  const emblem = view.titles.find((t) => t.worn)?.track ?? "fox";

  const show = (item: CastleItem) => {
    if (item.kind === "theme") {
      const look = THEME_LOOK[item.value];
      if (look) {
        setPreview((current) => ({ ...current, theme: item.value, season: look.season, time_of_day: look.time_of_day, weather: look.weather }));
      }
      return;
    }
    setPreview((current) => ({ ...current, theme: null, ...fieldPatch(FIELD_BY_KIND[item.kind], item.value) }));
  };

  const buy = async (item: CastleItem) => {
    setBusy(true);
    setMessage(null);
    try {
      await castleApi.buy(item.id);
      const next = await castleApi.apply(fieldPatch(FIELD_BY_KIND[item.kind], item.value));
      onChange(next);
      setPreview(next.appearance);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "";
      setMessage(detail.includes("not enough coins") ? "Не хватает монет" : "Не удалось купить");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-label="Примерка облика замка">
      <CastleStage
        freeArea={freeArea}
        openId={null}
        pulsing={[]}
        appearance={preview}
        emblem={emblem}
        onOpen={() => undefined}
      />
      <div className="fox-pad-top pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 px-4 pb-2">
        <p className="rounded-full bg-[#1a1230]/70 px-4 py-2 text-[14px] font-extrabold text-[#f6efe2]">
          Примерка: выбор виден сразу, покупка — на месте
        </p>
        <button
          type="button"
          onClick={onClose}
          className="pointer-events-auto rounded-full bg-[#1a1230]/70 px-4 py-2 text-[15px] font-extrabold text-[#ffd36e] press"
        >
          Готово
        </button>
      </div>
      <div className="absolute inset-x-0 bottom-0 z-10 space-y-2 bg-[#1a1230]/80 p-3 backdrop-blur">
        <div className="flex gap-1 overflow-x-auto" role="tablist">
          {Object.entries(CATEGORY_TITLES).map(([kind, title]) => (
            <button
              key={kind}
              type="button"
              role="tab"
              aria-selected={category === kind}
              onClick={() => setCategory(kind)}
              className={`whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-extrabold ${
                category === kind ? "bg-[#ffd36e] text-[#4a2a10]" : "bg-white/10 text-[#f6efe2]"
              }`}
            >
              {title}
            </button>
          ))}
        </div>
        <ul className="flex gap-2 overflow-x-auto pb-1">
          {items.map((item) => (
            <li key={item.id} className="shrink-0">
              <div className="flex w-36 flex-col items-center gap-1 rounded-2xl bg-white/10 p-2">
                <button
                  type="button"
                  aria-label={item.title_ru}
                  onClick={() => show(item)}
                  className="flex h-14 w-full items-center justify-center rounded-xl bg-black/20 px-1 text-center text-[12px] font-bold text-[#f6efe2]"
                >
                  <Thumb item={item} />
                  {!["season", "theme"].includes(item.kind) ? item.title_ru : null}
                </button>
                <span className="max-w-full truncate text-[12px] font-extrabold text-[#f6efe2]">{item.title_ru}</span>
                {item.owned ? (
                  <span className="text-[11px] font-bold text-[#9fe3b1]">есть</span>
                ) : !item.unlocked ? (
                  <span className="text-[11px] font-bold text-[#c9b8e8]">
                    {TRACK_TITLES[item.requires_track ?? ""] ?? "звание"} {item.requires_level} ур.
                  </span>
                ) : !item.purchasable ? (
                  <span className="text-[11px] font-bold text-[#c9b8e8]">только за звание</span>
                ) : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void buy(item)}
                    className="rounded-full bg-[#ffd36e] px-3 py-1 text-[12px] font-extrabold text-[#4a2a10] press"
                  >
                    Купить · {item.price}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {message ? <p className="text-center text-[13px] font-bold text-[#ffb3a6]" role="alert">{message}</p> : null}
      </div>
      {/* свободная область для вписывания сцены: весь экран минус лента */}
      <div ref={setFreeArea} className="pointer-events-none absolute inset-x-0 top-0" style={{ bottom: 170 }} aria-hidden />
    </div>
  );
}
