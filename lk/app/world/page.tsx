"use client";

import { Castle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Profile, WORLD_URL, WorldProgress } from "@/lib/api";
import { clearSession, getToken } from "@/lib/session";
import { fmt, useI18n } from "@/lib/i18n";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";

export default function WorldPage() {
  return (
    <CabinetPage>
      <Inner />
    </CabinetPage>
  );
}

function Inner() {
  const router = useRouter();
  const { t } = useI18n();
  const cab = useCabinet();
  const profiles: Profile[] = cab.me?.profiles ?? [];
  const activeId = cab.active?.id ?? null;
  const setActiveId = cab.setActiveId;
  const [progress, setProgress] = useState<WorldProgress | null>(null);
  const [error, setError] = useState("");
  const [entering, setEntering] = useState(false);

  const token = getToken();
  const active = profiles.find((p) => p.id === activeId) ?? profiles[0];


  const load = useCallback(async () => {
    if (!token || !active) return;
    setError("");
    try {
      const out = await api.worldProgress(token, active.student_id ?? 0);
      setProgress(out);
    } catch {
      setError(t.world.loadError);
    }
  }, [token, active, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onEnter() {
    if (!token || !active || entering) return;
    setEntering(true);
    setError("");
    try {
      const s = await api.worldSession(token, active.student_id ?? 0);
      const url = new URL(WORLD_URL);
      url.searchParams.set("world_token", s.session);
      url.searchParams.set("world_key", s.external_key);
      window.open(url.toString(), "_blank", "noopener");
    } catch {
      setError(t.world.enterError);
    } finally {
      setEntering(false);
    }
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

      <div className="k-legacy">
        <div className="dashboard-head">
          <div>
            <h1 className="dashboard-title">{t.world.title}</h1>
            <p className="dashboard-sub">
              {fmt(t.world.sub, { name: active ? active.child_name : "" })}
            </p>
          </div>
          <div className="topbar-spacer" />
          {false && profiles.length > 1 && (
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

        {error && <div className="alert alert-error">{error}</div>}

        {!progress ? (
          <div className="card center-card">
            <p className="card-sub" style={{ marginBottom: 0 }}>
              {t.common.loadingProgress}
            </p>
          </div>
        ) : !progress.linked ? (
          <div className="card world-hero">
            <div className="world-emoji" aria-hidden><Castle size={56} strokeWidth={2} /></div>
            <h2 className="card-title">{t.world.notStartedTitle}</h2>
            <p className="card-sub">
              {fmt(t.world.notStartedSub, { name: progress.child_name })}
            </p>
            <button className="btn btn-primary" onClick={() => void onEnter()} disabled={entering}>
              {entering ? t.world.entering : t.world.enter}
            </button>
          </div>
        ) : (
          <>
            <div className="stat-row">
              <div className="stat-card">
                <div className="stat-num">{progress.level}</div>
                <div className="stat-label">{t.world.level}</div>
              </div>
              <div className="stat-card">
                <div className="stat-num">{progress.xp}</div>
                <div className="stat-label">{t.world.xp}</div>
              </div>
              <div className="stat-card">
                <div className="stat-num">{progress.coins}</div>
                <div className="stat-label">{t.world.coins}</div>
              </div>
              <div className="stat-card">
                <div className="stat-num">{progress.streak_days}</div>
                <div className="stat-label">{t.world.streak}</div>
              </div>
            </div>

            {(progress.tracks?.length ?? 0) > 0 && (
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="widget-title" style={{ marginBottom: 12 }}>
                  {t.world.towers}
                </div>
                <div className="widget-body">
                  {progress.tracks!.map((tr) => (
                    <div key={tr.track} className="track-row">
                      <span className="track-name">
                        {tr.track === "spotlight" ? t.world.towerSpotlight : tr.track}
                      </span>
                      <span className="track-level">
                        {fmt(t.world.towerLevel, { level: tr.level })}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {progress.league && (
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="widget-title" style={{ marginBottom: 4 }}>
                  {t.world.league}
                </div>
                <div className="widget-body">
                  {fmt(t.world.leagueBody, { rank: progress.league.rank, xp: progress.league.weekly_xp })}
                </div>
              </div>
            )}

            <div className="card world-hero">
              <div className="world-emoji" aria-hidden><Castle size={56} strokeWidth={2} /></div>
              <p className="card-sub" style={{ marginBottom: 18 }}>
                {fmt(t.world.enterSubLinked, { name: progress.child_name })}
              </p>
              <button className="btn btn-primary" onClick={() => void onEnter()} disabled={entering}>
                {entering ? t.world.entering : t.world.enter}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
