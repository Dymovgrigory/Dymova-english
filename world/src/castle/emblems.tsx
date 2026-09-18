/**
 * Эмблемы веток званий — белый штамп на полотнище знамени. Вектор, без расхода кредитов.
 * viewBox 24×24, рисунок наследует currentColor.
 */
import type { JSX } from "react";

const PATHS: Record<string, JSX.Element> = {
  // Словесник — раскрытая книга
  lexicon: (
    <path d="M12 5c-2-1.4-4.5-2-7-2v14c2.5 0 5 .6 7 2 2-1.4 4.5-2 7-2V3c-2.5 0-5 .6-7 2zm0 13.5V6.8M5 8h4M5 11h4M15 8h4m-4 3h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  ),
  // Тренер — гантеля
  yard: (
    <path d="M4 9v6m3-9v12m10-12v12m3-9v6M7 12h10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  ),
  // Хранитель огня — пламя
  nest: (
    <path d="M12 3c1 3-4 5-4 9a4 4 0 008 0c0-1.5-.5-2.5-1-3.5-.8 1-1.2 1.5-1.2 2.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  ),
  // Чемпион — кубок
  glory: (
    <>
      <path d="M8 4h8v5a4 4 0 01-8 0V4zM8 5H5.5a2.5 2.5 0 002.6 2.5M16 5h2.5a2.5 2.5 0 01-2.6 2.5M12 13v4m-3 3h6m-6 0h6l-1-3h-4l-1 3z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  // Собиратель — звезда-наклейка
  stickers: (
    <path d="M12 4l2.2 4.6 5 .6-3.7 3.4 1 4.9-4.5-2.5-4.5 2.5 1-4.9L4.8 9.2l5-.6L12 4z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
  ),
  // Лиса по умолчанию — мордочка
  fox: (
    <>
      <path d="M5 4l3 3h8l3-3v7a7 7 0 01-14 0V4z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx="9.5" cy="11" r="0.6" fill="currentColor" />
      <circle cx="14.5" cy="11" r="0.6" fill="currentColor" />
      <path d="M12 13l-1 1.5h2L12 13z" fill="currentColor" />
    </>
  ),
};

export function Emblem({ id, className }: { id: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      {PATHS[id] ?? PATHS.fox}
    </svg>
  );
}
