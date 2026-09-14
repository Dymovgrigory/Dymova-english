"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");

  const enter = () => {
    const chosen = name.trim() || "Исследователь";
    window.localStorage.setItem("world.name", chosen);
    router.push("/world");
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-[#241a30] p-6">
      <Glass className="w-full max-w-md p-8 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фоксинбург</p>
        <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-extrabold leading-tight">
          Первый день в мире английского
        </h1>
        <p className="mt-3 text-sm text-white/60">
          Фокси уже ждёт тебя во дворе школы.
        </p>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Как тебя зовут?"
          className="mt-6 w-full rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-center outline-none focus:border-[#f5ed75]"
        />
        <div className="mt-6">
          <GameButton onClick={enter}>В Фоксинбург</GameButton>
        </div>
      </Glass>
    </main>
  );
}
