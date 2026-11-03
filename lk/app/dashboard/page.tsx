"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Profile } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";
import { fmt, useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

type Me = {
  account: { parent_name?: string; phone_masked?: string; guest?: boolean };
  profiles: Profile[];
};

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) {
      router.replace("/auth");
      return;
    }
    try {
      const data = await api.me(token);
      setMe(data as Me);
      setActiveId((prev) =>
        prev !== null && data.profiles.some((p) => p.id === prev)
          ? prev
          : (data.profiles[0]?.id ?? null),
      );
    } catch {
      clearSession();
      router.replace("/auth");
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onLogout() {
    const token = getToken();
    if (token) {
      try {
        await api.logout(token);
      } catch {
        /* сессия могла уже протухнуть — выходим всё равно */
      }
    }
    clearSession();
    router.replace("/auth");
  }

  if (!me) {
    return (
      <main className="shell-main">
        <div className="card center-card">
          <p className="card-sub" style={{ marginBottom: 0 }}>
            {t.common.loadingCabinet}
          </p>
        </div>
      </main>
    );
  }

  const active = me.profiles.find((p) => p.id === activeId) ?? me.profiles[0];

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="https://dymova-english.ru" target="_blank" rel="noopener">
            {t.common.brand}
            <span className="brand-badge">{t.common.lkBadge}</span>
          </a>
          <div className="topbar-spacer" />
          <span style={{ fontSize: 13, fontWeight: 700, opacity: 0.9 }}>
            {me.account.parent_name} · {me.account.phone_masked}
          </span>
          <LangSwitch />
          <button className="btn btn-light btn-sm" onClick={onLogout}>
            {t.common.logout}
          </button>
        </div>
      </header>

      <main className="shell-main">
        {error && <div className="alert alert-error">{error}</div>}
        {me.account.guest && (
          <div className="alert alert-info">{t.dashboard.guestBanner}</div>
        )}

        <div className="dashboard-head">
          <div>
            <h1 className="dashboard-title">{t.dashboard.title}</h1>
            <p className="dashboard-sub">
              {fmt(t.dashboard.sub, { name: active ? active.child_name : t.dashboard.profileFallback })}
            </p>
          </div>
          <div className="topbar-spacer" />
          {me.profiles.length > 1 && (
            <div className="profile-switch" role="tablist" aria-label={t.common.profilesAria}>
              {me.profiles.map((p) => (
                <button
                  key={p.id}
                  role="tab"
                  aria-selected={p.id === activeId}
                  className={
                    "profile-chip" + (p.id === activeId ? " profile-chip-active" : "")
                  }
                  onClick={() => setActiveId(p.id)}
                >
                  {p.child_name}
                </button>
              ))}
            </div>
          )}
        </div>

        {active && active.source === "crm" && active.active_groups.length > 0 && (
          <div className="widget" style={{ marginBottom: 18 }}>
            <div className="widget-title">{t.dashboard.groups}</div>
            <div className="widget-body">
              {active.active_groups.map((g) => g.caption).join(" · ")}
            </div>
          </div>
        )}

        <div className="widgets">
          <Widget
            title={t.dashboard.scheduleTitle}
            tag={t.dashboard.tagDone}
            icon={
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <rect x="3" y="4" width="18" height="18" rx="3" />
                <path d="M16 2v4M8 2v4M3 10h18" />
              </svg>
            }
          >
            {t.dashboard.scheduleBody}{" "}
            <a href="/schedule" style={{ fontWeight: 800 }}>{t.dashboard.scheduleLink}</a>
          </Widget>
          <Widget
            title={t.dashboard.wordsTitle}
            tag={t.dashboard.tagDone}
            icon={
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            }
          >
            {t.dashboard.wordsBody}{" "}
            <a href="/words" style={{ fontWeight: 800 }}>{t.dashboard.wordsLink}</a>
          </Widget>
          <Widget
            title={t.dashboard.worldTitle}
            tag={t.dashboard.tagDone}
            icon={
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 21h18M5 21V8l7-5 7 5v13" />
                <path d="M9 21v-6h6v6" />
              </svg>
            }
          >
            {t.dashboard.worldBody}{" "}
            <a href="/world" style={{ fontWeight: 800 }}>{t.dashboard.worldLink}</a>
          </Widget>
          <Widget
            title={t.dashboard.achTitle}
            tag={t.dashboard.tagSoon}
            icon={
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="8" r="6" />
                <path d="M15.5 13 17 22l-5-3-5 3 1.5-9" />
              </svg>
            }
          >
            {t.dashboard.achBody}
          </Widget>
        </div>
      </main>
    </>
  );
}

function Widget({
  title,
  tag,
  icon,
  children,
}: {
  title: string;
  tag: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="widget">
      <div className="widget-title">
        <span className="widget-icon">{icon}</span>
        {title}
      </div>
      <div className="widget-body">{children}</div>
      <span className="widget-tag">{tag}</span>
    </section>
  );
}
