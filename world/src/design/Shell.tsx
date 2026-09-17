"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

const TABS: { href: string; label: string; icon: IconName }[] = [
  { href: "/learn", label: "Путь", icon: "path" },
  { href: "/practice", label: "Тренировка", icon: "dumbbell" },
  { href: "/words", label: "Словарь", icon: "book" },
  { href: "/world", label: "Замок", icon: "castle" },
  { href: "/profile", label: "Профиль", icon: "user" },
];

/** Каркас разделов: нижнее меню на телефоне, левая колонка на широком экране. */
export function Shell({ children, top }: { children: ReactNode; top?: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="study flex min-h-dvh">
      <nav
        aria-label="Разделы"
        className="glass-dusk fixed inset-x-0 bottom-0 z-30 pb-[env(safe-area-inset-bottom)] lg:inset-y-0 lg:left-0 lg:right-auto lg:w-60 lg:pb-0"
      >
        <div className="hidden px-6 pb-4 pt-7 lg:block">
          <span className="font-fairy text-[28px] font-black tracking-tight text-[#ffd36e]">Фоксинбург</span>
          <p className="mt-0.5 text-[13px] font-bold text-[#c9bfd8]">Тренажёр к учебнику Spotlight</p>
        </div>
        <ul className="mx-auto flex max-w-lg justify-between px-2 lg:max-w-none lg:flex-col lg:gap-1 lg:px-3">
          {TABS.map((tab) => {
            const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
            return (
              <li key={tab.href} className="flex-1 lg:flex-none">
                <Link
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "flex flex-col items-center gap-0.5 rounded-2xl py-2 text-[11px] font-extrabold lg:flex-row lg:gap-3 lg:px-4 lg:py-3 lg:text-[16px]",
                    "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/60",
                    active ? "text-[#ffd36e] lg:bg-white/10 lg:ring-1 lg:ring-[#ffd36e]/40" : "text-[#c9bfd8] hover:text-[#f6efe2]",
                  ].join(" ")}
                >
                  <Icon name={tab.icon} size={26} />
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col pb-24 lg:pb-0 lg:pl-60">
        {top}
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
