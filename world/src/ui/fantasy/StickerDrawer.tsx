"use client";

import { useEffect, useState, type ReactNode } from "react";
import { FantasyButton, FantasyPanel } from "@/ui/fantasy/Chrome";

export type StickerItem = {
  id: string;
  title_ru: string;
  emoji?: string;
  owned: boolean;
};

const ART: Record<string, string> = {
  "sticker-family": "/world/ui/stickers/sticker-family.png",
  "sticker-school": "/world/ui/stickers/sticker-school.png",
  "sticker-room": "/world/ui/stickers/sticker-room.png",
  "sticker-pets": "/world/ui/stickers/sticker-pets.png",
  "sticker-food": "/world/ui/stickers/sticker-food.png",
  "sticker-play": "/world/ui/stickers/sticker-play.png",
  "sticker-satp": "/world/ui/stickers/sticker-satp.png",
  "sticker-hello": "/world/ui/stickers/sticker-hello.png",
  "sticker-perfect": "/world/ui/stickers/sticker-perfect.png",
  "sticker-streak": "/world/ui/stickers/sticker-streak.png",
  "sticker-rainbow": "/world/ui/stickers/sticker-rainbow.png",
};

export function stickerArt(id: string) {
  return ART[id] || null;
}

/** CTA + slide-up animated collection drawer. */
export function StickerCollection({
  stickers,
  ownedCount,
}: {
  stickers: StickerItem[];
  ownedCount: number;
}) {
  const [open, setOpen] = useState(false);
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setEntered(open));
    return () => window.cancelAnimationFrame(id);
  }, [open]);

  return (
    <>
      <FantasyButton onClick={() => setOpen(true)} tone="gold">
        Открыть коллекцию · {ownedCount}/{stickers.length || 11}
      </FantasyButton>

      {open ? (
        <div className="fixed inset-0 z-50 flex flex-col justify-end">
          <button
            type="button"
            aria-label="Закрыть коллекцию"
            className="absolute inset-0 bg-[#241a30]/65 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <div
            className={`relative z-10 max-h-[78dvh] overflow-y-auto rounded-t-[28px] border-t-2 border-[#f5ed75]/45 bg-[linear-gradient(180deg,rgba(36,26,48,0.96),rgba(26,18,40,0.98))] px-4 pb-8 pt-4 shadow-[0_-24px_60px_rgba(0,0,0,0.55)] transition-transform duration-500 ease-out ${
              entered ? "translate-y-0" : "translate-y-full"
            }`}
          >
            <div className="mx-auto mb-3 h-1 w-14 rounded-full bg-[#f5ed75]/80" />
            <FantasyPanel wide>
              <p className="text-center text-[10px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">
                Башня стикеров
              </p>
              <h3 className="mt-1 text-center font-[family-name:var(--font-display)] text-xl font-extrabold text-[#f5ed75]">
                Коллекция замка
              </h3>
            </FantasyPanel>

            <ul className="mx-auto mt-4 grid max-w-lg grid-cols-2 gap-4 sm:grid-cols-3">
              {stickers.map((it) => (
                <li key={it.id}>
                  <StickerCard item={it} />
                </li>
              ))}
            </ul>

            <div className="mx-auto mt-5 max-w-[min(92vw,22rem)]">
              <FantasyButton onClick={() => setOpen(false)} tone="ghost">
                Свернуть альбом
              </FantasyButton>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function StickerCard({ item }: { item: StickerItem }) {
  const art = stickerArt(item.id);
  return (
    <div
      className={`relative overflow-hidden rounded-[20px] border p-3 text-center transition ${
        item.owned
          ? "border-[#f5ed75]/55 bg-[linear-gradient(160deg,rgba(58,41,83,0.9),rgba(36,26,48,0.95))] shadow-[0_0_18px_rgba(245,237,117,0.2)]"
          : "border-white/10 bg-white/5 opacity-45 grayscale"
      }`}
      style={{ clipPath: "polygon(6% 0, 94% 0, 100% 10%, 100% 90%, 94% 100%, 6% 100%, 0 90%, 0 10%)" }}
    >
      {art ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={art} alt="" className="mx-auto h-36 w-36 object-contain drop-shadow-lg sm:h-40 sm:w-40" />
      ) : (
        <p className="py-8 font-[family-name:var(--font-display)] text-3xl font-extrabold text-[#f5ed75]/40">?</p>
      )}
      <p className="mt-2 font-[family-name:var(--font-display)] text-sm font-extrabold text-[#f5ed75]">
        {item.title_ru}
      </p>
      {!item.owned ? <p className="mt-0.5 text-[10px] font-bold text-white/50">ещё впереди</p> : null}
    </div>
  );
}

export function StickerPreviewRow({ stickers }: { stickers: StickerItem[] }) {
  const owned = stickers.filter((s) => s.owned).slice(0, 4);
  if (!owned.length) return null;
  return (
    <div className="mx-auto flex max-w-[min(92vw,22rem)] justify-center gap-2">
      {owned.map((s) => {
        const art = stickerArt(s.id);
        return art ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={s.id} src={art} alt="" className="h-14 w-14 object-contain drop-shadow" />
        ) : (
          <span
            key={s.id}
            className="grid h-14 w-14 place-items-center border border-[#f5ed75]/35 text-sm font-extrabold text-[#f5ed75]"
            style={{ clipPath: "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)" }}
          >
            ★
          </span>
        );
      })}
    </div>
  );
}

export function FantasyKicker({ children }: { children: ReactNode }) {
  return (
    <p className="text-center text-[10px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">{children}</p>
  );
}

export function FantasyTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-center font-[family-name:var(--font-display)] text-xl font-extrabold text-[#f5ed75] md:text-2xl">
      {children}
    </h2>
  );
}
