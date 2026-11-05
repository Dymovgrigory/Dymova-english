"use client";

import { useEffect, useState } from "react";

/** Адрес личного кабинета школы (возврат из Мира в ту же вкладку). */
export const LK_URL = process.env.NEXT_PUBLIC_LK_URL || "https://lms.dymova-english.ru/dashboard";
const FROM_LK_KEY = "fox_from_lk";

/** Отмечаем, что ребёнок пришёл из ЛК (?from=lk) — тогда показываем кнопку возврата. */
export function rememberFromLk(): void {
  try {
    window.localStorage.setItem(FROM_LK_KEY, "1");
  } catch {
    /* хранилище недоступно — кнопку всё равно покажем по флагу в URL */
  }
}

/** Кнопка «Личный кабинет» в Мире: возвращает в ЛК в этой же вкладке. */
export function BackToLk() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    let v = false;
    try {
      v = window.localStorage.getItem(FROM_LK_KEY) === "1" || new URLSearchParams(window.location.search).get("from") === "lk";
    } catch {
      v = new URLSearchParams(window.location.search).get("from") === "lk";
    }
    // В Telegram Mini App своя навигация — там кнопку не показываем.
    const tg = (window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData;
    setShow(v && !tg);
  }, []);
  if (!show) return null;
  return (
    <a
      href={LK_URL}
      className="fixed left-3 top-[max(0.75rem,var(--fox-safe-top,0px))] z-50 inline-flex items-center gap-2 rounded-full bg-[#241a30]/85 px-4 py-2 text-[14px] font-extrabold text-[#ffd36e] shadow-lg ring-1 ring-[#ffd36e]/40 backdrop-blur hover:bg-[#241a30] lg:left-auto lg:right-4"
    >
      <span aria-hidden="true">←</span> Личный кабинет
    </a>
  );
}
