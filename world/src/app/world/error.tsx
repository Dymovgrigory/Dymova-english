"use client";

import { useEffect } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";

/** Error boundary маршрута /world: сбой рендера мира не должен ронять всё приложение. */
export default function WorldError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Фоксинбург: сбой на странице мира", error);
  }, [error]);

  return (
    <main className="grid h-dvh w-full place-items-center bg-[#241a30] p-4">
      <Glass className="w-full max-w-md p-6 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фоксинбург</p>
        <p className="mt-3 font-[family-name:var(--font-display)] text-xl font-extrabold text-white">
          Фоксинбург не отвечает
        </p>
        <p className="mt-2 text-sm text-white/70">
          Что-то пошло не так, пока мир загружался. Попробуй ещё раз — обычно это помогает.
        </p>
        <div className="mt-5 flex justify-center">
          <GameButton onClick={reset}>Попробовать снова</GameButton>
        </div>
      </Glass>
    </main>
  );
}
