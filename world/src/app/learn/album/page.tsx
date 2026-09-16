"use client";

import Link from "next/link";
import { WorldBar } from "@/ui/WorldBar";
import { useEffect, useState } from "react";
import { worldApi, type Player } from "@/lib/api";
import { FoxiGuide } from "@/ui/FoxiGuide";
import { RoomKicker, RoomLead, RoomTitle } from "@/ui/RoomChrome";
import { StickerCollection, stickerArt } from "@/ui/fantasy/StickerDrawer";

export default function AlbumPage() {
  const [items, setItems] = useState<{ id: string; title_ru: string; emoji: string; owned: boolean }[]>([]);
  const [owned, setOwned] = useState(0);
  const [total, setTotal] = useState(0);
  const [player, setPlayer] = useState<Player | null>(null);
  const [hearts, setHearts] = useState(5);

  useEffect(() => {
    let name = "Исследователь";
    try {
      name = window.localStorage.getItem("world.name") || name;
    } catch {
      /* private mode */
    }
    void worldApi
      .ensurePlayer(name)
      .then(() => Promise.all([worldApi.getStickers(), worldApi.getLearnHome().catch(() => null)]))
      .then(([data, home]) => {
        setItems(data.items);
        setOwned(data.owned);
        setTotal(data.total);
        if (home) {
          setPlayer(home.player);
          setHearts(home.hearts?.current ?? 5);
        }
      });
  }, []);

  return (
    <main className="relative min-h-dvh overflow-hidden bg-[#241a30] px-4 py-6 text-white">
      <header className="relative z-20 mb-2">
        <WorldBar stickers={owned} player={player} hearts={hearts} xp={player?.xp} coins={player?.coins} />
      </header>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center opacity-50"
        style={{ backgroundImage: "url(/world/cinematic/library-courtyard.png)" }}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#241a30]/45 via-[#241a30]/75 to-[#241a30]" />
      <div aria-hidden className="world-embers pointer-events-none absolute inset-0" />

      <div className="relative z-10 mx-auto max-w-2xl">
        <Link href="/learn">
          <span
            className="inline-flex min-h-[44px] items-center border border-[#f5ed75]/45 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] px-4 py-2 text-sm font-extrabold text-[#f5ed75]"
            style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
          >
            ← К урокам
          </span>
        </Link>
        <div className="mt-4">
          <FoxiGuide
            pose="cheer"
            tone="dark"
            kicker="Альбом"
            line={`У тебя ${owned} из ${total} стикеров. Закрой урок — получишь новый.`}
          />
        </div>
        <div className="mt-6 text-center">
          <RoomKicker>Башня стикеров</RoomKicker>
          <RoomTitle>Стикеры замка</RoomTitle>
          <RoomLead>Каждый стикер — след слова, сказанного вслух.</RoomLead>
        </div>
        <div className="mt-6 flex flex-col items-center gap-3">
          <div className="flex justify-center gap-2">
            {items
              .filter((i) => i.owned)
              .slice(0, 4)
              .map((it) => {
                const art = stickerArt(it.id);
                return art ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img key={it.id} src={art} alt="" className="h-16 w-16 object-contain drop-shadow" />
                ) : null;
              })}
          </div>
          <StickerCollection stickers={items} ownedCount={owned} />
        </div>
      </div>
    </main>
  );
}
