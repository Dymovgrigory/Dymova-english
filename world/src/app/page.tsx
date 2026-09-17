"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { v2, verifiedPlayer } from "@/lib/v2/client";

/** Вход: новичок — знакомство «Мой класс», ученик с профилем — сразу на путь. */
export default function EntryPage() {
  const router = useRouter();

  useEffect(() => {
    verifiedPlayer()
      .then((known) => (known ? v2.profile() : Promise.reject(new Error("new player"))))
      .then(() => router.replace("/learn"))
      .catch(() => router.replace("/onboarding"));
  }, [router]);

  return (
    <div className="study flex min-h-dvh items-center justify-center">
      <p className="font-heading text-[28px] font-extrabold text-royal" role="status">
        Фоксинбург
      </p>
    </div>
  );
}
