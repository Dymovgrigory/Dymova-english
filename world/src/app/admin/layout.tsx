"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { adminApi, adminToken, type AdminMe } from "@/lib/v2/admin";

/** Админская рамка: проверка токена, шапка, вложенная навигация. Страница логина — без рамки. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/admin/login";
  const [me, setMe] = useState<AdminMe | null>(null);

  useEffect(() => {
    if (isLogin) return;
    if (!adminToken()) {
      router.replace("/admin/login");
      return;
    }
    let alive = true;
    adminApi
      .me()
      .then((res) => {
        if (alive) setMe(res);
      })
      .catch(() => {
        router.replace("/admin/login");
      });
    return () => {
      alive = false;
    };
  }, [isLogin, router, pathname]);

  if (isLogin) return <>{children}</>;

  if (!me) {
    return (
      <div className="study-plain flex min-h-dvh items-center justify-center text-[#6f5843]">Проверяем доступ…</div>
    );
  }

  const logout = async () => {
    try {
      await adminApi.logout();
    } catch {
      /* сессия могла уже умереть */
    }
    router.replace("/admin/login");
  };

  return (
    <div className="study-plain min-h-dvh">
      <header className="mat-stone sticky top-0 z-20 text-[#f6efe2]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <div className="text-lg font-extrabold tracking-wide">Foxinburg World — Админ</div>
          <nav className="flex items-center gap-1 text-sm font-bold">
            <Link
              href="/admin/students"
              className={`min-h-10 rounded-xl px-3 py-2 hover:bg-white/10 ${
                pathname.startsWith("/admin/students") ? "bg-white/15 text-[#ffe89a]" : ""
              }`}
            >
              Участники
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-[#c9bfd8]">{me.login}</span>
            <button
              type="button"
              onClick={logout}
              className="min-h-10 rounded-xl bg-white/10 px-4 font-bold hover:bg-white/20 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
