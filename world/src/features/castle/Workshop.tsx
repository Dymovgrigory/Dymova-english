"use client";

import { useState } from "react";

import { Button } from "@/design/Button";
import { Icon } from "@/design/Icon";
import { ApiError } from "@/lib/api";
import { castleApi, type Appearance, type CastleItem, type CastleView } from "@/lib/v2/castle";

const KIND_TITLES: Record<string, string> = {
  season: "Сезон",
  time: "Время суток",
  weather: "Погода",
  banner: "Знамя",
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

/** Витрина облика: покупка и применение. Все проверки делает сервер, здесь только показ. */
export function Workshop({ view, onChange }: { view: CastleView; onChange: (view: CastleView) => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const act = async (run: () => Promise<CastleView>, failure: string) => {
    setBusy(true);
    try {
      onChange(await run());
      setMessage(null);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "";
      setMessage(detail.includes("not enough coins") ? "Не хватает монет" : failure);
    } finally {
      setBusy(false);
    }
  };

  const isApplied = (item: CastleItem) => view.appearance[FIELD_BY_KIND[item.kind]] === item.value;

  return (
    <div className="space-y-4">
      {Object.entries(KIND_TITLES).map(([kind, title]) => {
        const items = view.catalog.filter((item) => item.kind === kind);
        if (items.length === 0) return null;
        return (
          <section key={kind} className="space-y-2">
            <h3 className="text-[15px] font-extrabold text-ink">{title}</h3>
            <ul className="grid grid-cols-2 gap-2">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    disabled={busy || !item.unlocked}
                    onClick={() =>
                      item.owned
                        ? act(
                            () => castleApi.apply(fieldPatch(FIELD_BY_KIND[item.kind], item.value)),
                            "Не удалось применить",
                          )
                        : act(() => castleApi.buy(item.id), "Не удалось купить")
                    }
                    className={[
                      "flex w-full items-center justify-between gap-2 rounded-2xl px-3 py-2 text-left",
                      isApplied(item) ? "mat-brass" : "mat-enamel",
                      item.unlocked ? "" : "opacity-60",
                    ].join(" ")}
                  >
                    <span className="text-[15px] font-extrabold text-ink">{item.title_ru}</span>
                    {item.owned ? (
                      <span className="text-[13px] font-bold text-ink-soft">
                        {isApplied(item) ? "выбрано" : "есть"}
                      </span>
                    ) : item.unlocked ? (
                      <span className="inline-flex items-center gap-1 text-[15px] font-extrabold text-[#d69e00]">
                        <Icon name="coin" size={16} />
                        {item.price}
                      </span>
                    ) : (
                      <span className="text-[12px] font-bold text-ink-soft">
                        {TRACK_TITLES[item.requires_track ?? ""] ?? "звание"} {item.requires_level} ур.
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {message ? <p className="text-center text-[15px] font-bold text-[#a82f25]">{message}</p> : null}
      <Button block variant="paper" onClick={() => void act(() => castleApi.get(), "Не удалось обновить")}>
        Обновить витрину
      </Button>
    </div>
  );
}
