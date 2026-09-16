"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { worldApi } from "@/lib/api";
import { FoxiGuide } from "@/ui/FoxiGuide";

export default function AlbumPage() {
  const [items, setItems] = useState<{ id: string; title_ru: string; emoji: string; owned: boolean }[]>([]);
  const [owned, setOwned] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let name = "Исследователь";
    try {
      name = window.localStorage.getItem("world.name") || name;
    } catch {
      /* private mode */
    }
    void worldApi.ensurePlayer(name).then(() => worldApi.getStickers()).then((data) => {
      setItems(data.items);
      setOwned(data.owned);
      setTotal(data.total);
    });
  }, []);

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#241a30] px-4 py-6 text-white">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center opacity-50"
        style={{ backgroundImage: "url(/world/cinematic/library-courtyard.jpg)" }}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#241a30]/45 via-[#241a30]/75 to-[#241a30]" />
      <div aria-hidden className="world-embers pointer-events-none absolute inset-0" />

      <div className="relative z-10 mx-auto max-w-2xl">
        <Link
          href="/learn"
          className="inline-flex rounded-full border border-white/15 bg-[#241a30]/70 px-3 py-1.5 text-sm font-extrabold text-[#f5ed75] backdrop-blur"
        >
          ← К урокам
        </Link>
        <div className="mt-4">
          <FoxiGuide
            pose="cheer"
            tone="dark"
            kicker="Альбом"
            line={`У тебя ${owned} из ${total} стикеров. Закрой урок — получишь новый.`}
          />
        </div>
        <p className="mt-6 text-[11px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">Foxinburg</p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl font-extrabold text-[#f5ed75]">
          Стикеры замка
        </h1>
        <ul className="mt-6 grid grid-cols-3 gap-3">
          {items.map((it) => (
            <li
              key={it.id}
              className={`rounded-3xl border p-4 text-center backdrop-blur-md ${
                it.owned
                  ? "border-[#f5ed75]/60 bg-[#f5ed75]/15 shadow-[0_8px_0_rgba(0,0,0,0.25)]"
                  : "border-white/10 bg-[#241a30]/55 opacity-45 grayscale"
              }`}
            >
              <p className="text-4xl">{it.emoji}</p>
              <p className="mt-2 text-xs font-extrabold text-white">{it.title_ru}</p>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
