"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Profile } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";
import { fmt, useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

type Lesson = {
  id: number;
  date: string;
  starts_at: string;
  ends_at: string;
  group: { id: number; caption: string };
  filial: { id: number; caption: string };
  attendance: "visited" | "missed" | "unknown";
};

type Schedule = {
  student_id: number;
  child_name: string;
  from: string;
  to: string;
  lessons: Lesson[];
};

const DAY_MS = 24 * 60 * 60 * 1000;

function mondayOf(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}

function fmtDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtTime(iso: string, locale: string): string {
  // BigBen отдаёт UTC; браузер пользователя переводит в локальное время.
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

export default function SchedulePage() {
  const router = useRouter();
  const { t, lang } = useI18n();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [weekStart, setWeekStart] = useState<Date>(() => mondayOf(new Date()));
  const [data, setData] = useState<Schedule | null>(null);
  const [error, setError] = useState("");

  const token = getToken();
  const active = profiles.find((p) => p.id === activeId) ?? profiles[0];

  useEffect(() => {
    if (!token) {
      router.replace("/auth");
      return;
    }
    api
      .me(token)
      .then((me) => {
        setProfiles(me.profiles);
        setActiveId(me.profiles[0]?.id ?? null);
      })
      .catch(() => {
        clearSession();
        router.replace("/auth");
      });
  }, [token, router]);

  const load = useCallback(async () => {
    if (!token || !active?.student_id) return;
    setError("");
    try {
      const to = new Date(weekStart.getTime() + 6 * DAY_MS);
      const out = await api.schedule(
        token,
        active.student_id,
        fmtDate(weekStart),
        fmtDate(to),
      );
      setData(out);
    } catch {
      setError(t.schedule.loadError);
    }
  }, [token, active, weekStart, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const byDay = useMemo(() => {
    const map = new Map<string, Lesson[]>();
    for (const l of data?.lessons ?? []) {
      const list = map.get(l.date) ?? [];
      list.push(l);
      map.set(l.date, list);
    }
    return map;
  }, [data]);

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * DAY_MS));
  }, [weekStart]);

  function shiftWeek(delta: number) {
    setWeekStart((w) => new Date(w.getTime() + delta * 7 * DAY_MS));
  }

  async function onLogout() {
    if (token) {
      try {
        await api.logout(token);
      } catch { /* уже протух */ }
    }
    clearSession();
    router.replace("/auth");
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="/dashboard">
            {t.common.brand}
            <span className="brand-badge">{t.common.lkBadge}</span>
          </a>
          <div className="topbar-spacer" />
          <LangSwitch />
          <button className="btn btn-light btn-sm" onClick={onLogout}>
            {t.common.logout}
          </button>
        </div>
      </header>

      <main className="shell-main">
        <div className="dashboard-head">
          <div>
            <h1 className="dashboard-title">{t.schedule.title}</h1>
            <p className="dashboard-sub">
              {fmt(t.schedule.sub, { name: active ? active.child_name : "" })}
            </p>
          </div>
          <div className="topbar-spacer" />
          {profiles.length > 1 && (
            <div className="profile-switch" role="tablist" aria-label={t.common.profilesAria}>
              {profiles.map((p) => (
                <button
                  key={p.id}
                  role="tab"
                  aria-selected={p.id === active?.id}
                  className={
                    "profile-chip" + (p.id === active?.id ? " profile-chip-active" : "")
                  }
                  onClick={() => setActiveId(p.id)}
                >
                  {p.child_name}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="week-nav">
          <button className="btn btn-ghost btn-sm" onClick={() => shiftWeek(-1)}>
            {t.schedule.weekBack}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setWeekStart(mondayOf(new Date()))}>
            {t.schedule.weekCurrent}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => shiftWeek(1)}>
            {t.schedule.weekFwd}
          </button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {!data ? (
          <div className="card center-card">
            <p className="card-sub" style={{ marginBottom: 0 }}>{t.common.loadingSchedule}</p>
          </div>
        ) : byDay.size === 0 ? (
          <div className="card">
            <p className="card-sub" style={{ marginBottom: 0 }}>
              {t.schedule.empty}
            </p>
          </div>
        ) : (
          <div className="days">
            {days.map((d) => {
              const key = fmtDate(d);
              const lessons = byDay.get(key);
              if (!lessons) return null;
              const today = fmtDate(new Date()) === key;
              return (
                <section key={key} className="day">
                  <h2 className="day-title">
                    {t.schedule.wd[d.getDay()]}, {d.getDate()} {t.schedule.months[d.getMonth()]}
                    {today && <span className="day-today">{t.schedule.today}</span>}
                  </h2>
                  <div className="lessons">
                    {lessons.map((l) => (
                      <article key={l.id} className="lesson">
                        <div className="lesson-time">
                          {fmtTime(l.starts_at, lang)}–{fmtTime(l.ends_at, lang)}
                        </div>
                        <div className="lesson-body">
                          <div className="lesson-group">{l.group?.caption}</div>
                          <div className="lesson-filial">{l.filial?.caption}</div>
                        </div>
                        <span className={"mark mark-" + l.attendance}>
                          {l.attendance === "visited"
                            ? t.schedule.visited
                            : l.attendance === "missed"
                              ? t.schedule.missed
                              : t.schedule.unknown}
                        </span>
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
