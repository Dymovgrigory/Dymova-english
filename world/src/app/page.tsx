"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");

  const enter = (href: string) => {
    const chosen = name.trim() || "Исследователь";
    window.localStorage.setItem("world.name", chosen);
    router.push(href);
  };

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden p-6">
      <div
        aria-hidden
        className="absolute inset-0 bg-[#241a30] bg-cover bg-center"
        style={{ backgroundImage: "url(/world/foxinburg-establishing-v1.png)" }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#241a30] via-[#241a30]/55 to-[#241a30]/25" />
      <Glass className="relative w-full max-w-md p-8 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фоксинбург</p>
        <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-extrabold leading-tight">
          Учимся с Foxy
        </h1>
        <p className="mt-3 text-sm text-white/70">
          Сначала 1 класс: Foxy учит говорить, как на занятии. Потом 72 урока чтения по звукам.
        </p>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Как тебя зовут?"
          className="mt-6 w-full rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-center outline-none focus:border-[#f5ed75]"
        />
        <div className="mt-6 flex flex-col gap-3">
          <GameButton onClick={() => enter("/learn")}>Учить с Foxy</GameButton>
          <button
            onClick={() => enter("/world")}
            className="text-sm text-white/70 underline-offset-4 hover:underline"
          >
            Сначала в замок
          </button>
        </div>
      </Glass>
    </main>
  );
}
