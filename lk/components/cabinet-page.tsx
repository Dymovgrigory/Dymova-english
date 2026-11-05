"use client";

import { CabinetProvider } from "@/lib/cabinet";
import AppShell from "@/components/app-shell";

/** Страница кабинета: контекст (аккаунт, ребёнок, статистика) + каркас с меню. */
export default function CabinetPage({ children, bare = false }: { children: React.ReactNode; bare?: boolean }) {
  return <CabinetProvider>{bare ? children : <AppShell>{children}</AppShell>}</CabinetProvider>;
}
