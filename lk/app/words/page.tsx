"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Profile, WordSet, WordStats } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";
import { fmt, useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

export default function WordsPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [sets, setSets] = useState<WordSet[]>([]);
  const [stats, setStats] = useState<WordStats | null>(null);
  const [error, setError] = useState("");

  const token = getToken();
  const active = profiles.find((p) => p.id === activeId) ?? profiles[0];

  const load = useCallback(async () => {
    if (!token || !active) return;
    setError("");
    try {
      const sid = active.student_id ?? 0;
      const [out, st] = await Promise.all([
        api.wordSets(token, sid),
        api.wordStats(token, sid),
      ]);
      setSets(out.sets);
      setStats(st);
    } catch {
      setError(t.words.loadError);
    }
  }, [token, active, t]);

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

  useEffect(() => {
    void load();
  }, [load]);

  async function onLogout() {
    if (token) {
      try {
        await api.logout(token);
      } catch { /* уже протух */ }
    }
    clearSession();
    router.replace("/auth");
  }

  const kindLabel = (kind: string): string =>
    kind === "level"
      ? t.words.kindLevel
      : kind === "book"
        ? t.words.kindBook
        : kind === "topic"
          ? t.words.kindTopic
          : kind;

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
            <h1 className="dashboard-title">{t.words.title}</h1>
            <p className="dashboard-sub">
              {fmt(t.words.sub, { name: active ? active.child_name : "" })}
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

        {stats && (
          <div className="stat-row">
            <div className="stat-card">
              <div className="stat-num">{stats.learned_words}</div>
              <div className="stat-label">{t.words.learned}</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">{stats.due_today}</div>
              <div className="stat-label">{t.words.dueToday}</div>
            </div>
            <div className="stat-card">
              <div className="stat-num">
                {stats.answers_total
                  ? Math.round((stats.answers_correct / stats.answers_total) * 100)
                  : 0}
                %
              </div>
              <div className="stat-label">{t.words.accuracy}</div>
            </div>
          </div>
        )}

        {error && <div className="alert alert-error">{error}</div>}

        {sets.length === 0 && !error ? (
          <div className="card">
            <p className="card-sub" style={{ marginBottom: 0 }}>
              {t.words.empty}
            </p>
          </div>
        ) : (
          <div className="set-grid">
            {sets.map((s) => {
              const p = s.progress;
              const pct = p.total ? Math.round((p.learned / p.total) * 100) : 0;
              return (
                <article key={s.id} className="set-card">
                  <div className="set-kind">
                    {kindLabel(s.kind)}
                    {s.cefr ? ` · ${s.cefr.toUpperCase()}` : ""}
                  </div>
                  <h2 className="set-title">{s.title}</h2>
                  <div className="set-progress">
                    <div className="set-progress-bar">
                      <div
                        className="set-progress-fill"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="set-progress-num">
                      {fmt(t.words.setProgress, { learned: p.learned, total: p.total, due: p.due })}
                    </div>
                  </div>
                  <a
                    className="btn btn-primary btn-sm set-train-btn"
                    href={`/words/train/${s.id}?student=${active?.student_id ?? 0}`}
                  >
                    {t.words.train}
                  </a>
                </article>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
