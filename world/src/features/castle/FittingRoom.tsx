"use client";

import { useState } from "react";

import { BANNER_HEX } from "@/castle/decor";
import { CastleStage } from "@/features/castle/CastleStage";
import { ApiError } from "@/lib/api";
import { castleApi, type Appearance, type CastleItem, type CastleView, type DecorItem } from "@/lib/v2/castle";

const CATEGORY_TITLES: Record<string, string> = {
  season: "Сезон",
  time: "Время суток",
  weather: "Погода",
  banner: "Знамя",
  decor: "Украшения",
};

type Field = "season" | "time_of_day" | "weather" | "banner_color";

const FIELD_BY_KIND: Record<string, Field> = {
  season: "season",
  time: "time_of_day",
  weather: "weather",
  banner: "banner_color",
};

/** Один слой облика для POST /appearance: strict TS не даёт собрать объект вычисляемым ключом. */
function fieldPatch(field: Field, value: string): Partial<Appearance> {
  if (field === "season") return { season: value };
  if (field === "time_of_day") return { time_of_day: value };
  if (field === "weather") return { weather: value };
  return { banner_color: value };
}

const TRACK_TITLES: Record<string, string> = {
  lexicon: "Словесник",
  yard: "Тренер",
  nest: "Хранитель огня",
  glory: "Чемпион",
  stickers: "Собиратель",
};

/** Миниатюра варианта в ленте: картинка сезона, цвет знамени, предмет или подпись. */
function Thumb({ item }: { item: CastleItem }) {
  if (item.kind === "decor") {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`/content/castle/decor/${item.id}.webp`} alt="" className="h-12 w-12 object-contain" />;
  }
  if (item.kind === "season") {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={`/content/castle/seasons/${item.value}.webp`} alt="" className="h-12 w-16 rounded-lg object-cover" />;
  }
  if (item.kind === "banner") {
    return <span className="block h-12 w-12 rounded-xl border-2 border-white/60" style={{ background: BANNER_HEX[item.value] }} />;
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
  const [decor, setDecor] = useState<DecorItem[]>(view.decor);
  const [category, setCategory] = useState<string>("season");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [freeArea, setFreeArea] = useState<HTMLDivElement | null>(null);

  const items = view.catalog.filter((item) => item.kind === category);
  const emblem = view.titles.find((t) => t.worn)?.track ?? "fox";
  const decorActive = new Map(decor.map((d) => [d.item_id, d.active]));

  /** Украшение: купленное — сразу ставится/снимается на сервере; некупленное — локальная примерка. */
  const toggleDecor = async (item: CastleItem) => {
    const active = decorActive.get(item.id) ?? false;
    if (item.owned) {
      setBusy(true);
      setMessage(null);
      try {
        const next = await castleApi.apply(active ? { decor_off: [item.id] } : { decor_on: [item.id] });
        onChange(next);
        setDecor(next.decor);
      } catch {
        setMessage("Не удалось применить украшение");
      } finally {
        setBusy(false);
      }
      return;
    }
    setDecor((current) => {
      const existing = current.find((d) => d.item_id === item.id);
      if (existing) return current.map((d) => (d.item_id === item.id ? { ...d, active: !active } : d));
      // Примерка некупленного украшения — просто ставим на его точку локально.
      return [...current, { item_id: item.id, anchor: item.anchor ?? "meadow", title_ru: item.title_ru, active: true }];
    });
  };

  const show = (item: CastleItem) => {
    if (item.kind === "decor") {
      void toggleDecor(item);
      return;
    }
    setPreview((current) => ({ ...current, ...fieldPatch(FIELD_BY_KIND[item.kind], item.value) }));
  };

  const buy = async (item: CastleItem) => {
    setBusy(true);
    setMessage(null);
    try {
      let next = await castleApi.buy(item.id);
      if (item.kind !== "decor") {
        next = await castleApi.apply(fieldPatch(FIELD_BY_KIND[item.kind], item.value));
      }
      onChange(next);
      setPreview(next.appearance);
      setDecor(next.decor);
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
        decor={decor}
        emblem={emblem}
        onOpen={() => undefined}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between p-4">
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
          {items.map((item) => {
            const placed = item.kind === "decor" && (decorActive.get(item.id) ?? false);
            return (
            <li key={item.id} className="shrink-0">
              <div className="flex w-36 flex-col items-center gap-1 rounded-2xl bg-white/10 p-2">
                <button
                  type="button"
                  aria-label={item.title_ru}
                  disabled={busy && item.kind === "decor" && item.owned}
                  onClick={() => show(item)}
                  className={`flex h-14 w-full items-center justify-center rounded-xl bg-black/20 px-1 text-center text-[12px] font-bold text-[#f6efe2] ${
                    placed ? "ring-2 ring-[#ffd36e]" : ""
                  }`}
                >
                  <Thumb item={item} />
                  {!["decor", "season", "banner"].includes(item.kind) ? item.title_ru : null}
                </button>
                <span className="max-w-full truncate text-[12px] font-extrabold text-[#f6efe2]">{item.title_ru}</span>
                {item.kind === "decor" && item.owned ? (
                  <span className={`text-[11px] font-bold ${placed ? "text-[#9fe3b1]" : "text-[#c9b8e8]"}`}>
                    {placed ? "стоит на замке — нажми, чтобы убрать" : "снято — нажми, чтобы поставить"}
                  </span>
                ) : item.kind === "decor" && placed ? (
                  <span className="text-[11px] font-bold text-[#9fe3b1]">на сцене · примерка</span>
                ) : item.owned ? (
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
            );
          })}
        </ul>
        {message ? <p className="text-center text-[13px] font-bold text-[#ffb3a6]" role="alert">{message}</p> : null}
      </div>
      {/* свободная область для вписывания сцены: весь экран минус лента */}
      <div ref={setFreeArea} className="pointer-events-none absolute inset-x-0 top-0" style={{ bottom: 170 }} aria-hidden />
    </div>
  );
}
