"use client";

// Общий контекст кабинета: аккаунт, выбранный ребёнок, игровая статистика.
// Один запрос /me на всё приложение; выбранный профиль помнится в браузере.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Profile, WordStats } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";

const ACTIVE_KEY = "lk_active_profile";

type Me = {
  account: { parent_name?: string; phone_masked?: string; guest?: boolean };
  profiles: Profile[];
};

type Cabinet = {
  token: string | null;
  me: Me | null;
  active: Profile | null;
  studentId: number;
  setActiveId: (id: number) => void;
  stats: WordStats | null;
  refreshStats: () => Promise<void>;
  logout: () => Promise<void>;
};

const Ctx = createContext<Cabinet | null>(null);

export function CabinetProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [activeId, setActive] = useState<number | null>(null);
  const [stats, setStats] = useState<WordStats | null>(null);

  useEffect(() => {
    const tk = getToken();
    if (!tk) {
      router.replace("/auth");
      return;
    }
    setToken(tk);
    api
      .me(tk)
      .then((data) => {
        setMe(data as Me);
        const saved = Number(window.localStorage.getItem(ACTIVE_KEY) || 0);
        const pick = data.profiles.find((p) => p.id === saved) ?? data.profiles[0];
        setActive(pick ? pick.id : null);
      })
      .catch(() => {
        clearSession();
        router.replace("/auth");
      });
  }, [router]);

  const active = useMemo(
    () => me?.profiles.find((p) => p.id === activeId) ?? me?.profiles[0] ?? null,
    [me, activeId],
  );
  const studentId = active?.student_id ?? 0;

  const refreshStats = useCallback(async () => {
    if (!token || !active) return;
    try {
      setStats(await api.wordStats(token, active.student_id ?? 0));
    } catch {
      /* статистика не критична для работы кабинета */
    }
  }, [token, active]);

  useEffect(() => {
    void refreshStats();
  }, [refreshStats]);

  const setActiveId = (id: number) => {
    setActive(id);
    window.localStorage.setItem(ACTIVE_KEY, String(id));
  };

  const logout = async () => {
    if (token) {
      try {
        await api.logout(token);
      } catch {
        /* сессия могла уже истечь */
      }
    }
    clearSession();
    router.replace("/auth");
  };

  return (
    <Ctx.Provider value={{ token, me, active, studentId, setActiveId, stats, refreshStats, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useCabinet(): Cabinet {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCabinet outside CabinetProvider");
  return v;
}
