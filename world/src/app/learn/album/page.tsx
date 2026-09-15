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
    <main className="min-h-dvh bg-[#f7f1e4] px-4 py-6 text-[#241a30]">
      <div className="mx-auto max-w-2xl">
        <Link href="/learn" className="text-sm text-[#241a30]/55">
          ← К урокам
        </Link>
        <FoxiGuide
          pose="cheer"
          kicker="Альбом"
          line={`У тебя ${owned} из ${total} стикеров. Закрой урок — получишь новый.`}
        />
        <h1 className="mt-5 text-3xl font-extrabold">Стикеры Фоксинбурга</h1>
        <ul className="mt-6 grid grid-cols-3 gap-3">
          {items.map((it) => (
            <li
              key={it.id}
              className={`rounded-3xl border bg-white p-4 text-center shadow-[0_6px_0_rgba(36,26,48,0.06)] ${
                it.owned ? "border-[#f5ed75] bg-[#f5ed75]/20" : "border-[#241a30]/10 opacity-40 grayscale"
              }`}
            >
              <p className="text-4xl">{it.emoji}</p>
              <p className="mt-2 text-xs font-extrabold">{it.title_ru}</p>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
