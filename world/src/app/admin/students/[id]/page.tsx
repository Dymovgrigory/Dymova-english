"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ApiError, humanizeError } from "@/lib/api";
import {
  adminApi,
  clearAdminToken,
  type AdminAuditItem,
  type AdminStudentDetail,
  type IdentityPatch,
} from "@/lib/v2/admin";
import { Button } from "@/design/Button";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("ru-RU");
}

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("ru-RU");
}

type PendingAction = {
  title: string;
  body: string;
  run: () => Promise<void>;
};

export default function AdminStudentPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();

  const [reload, setReload] = useState(0);
  type Result = {
    key: string;
    detail?: AdminStudentDetail;
    audit?: AdminAuditItem[];
    notFound?: boolean;
    error?: string;
  };
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busy, setBusy] = useState(false);

  const mapError = useCallback(
    (err: unknown, fallback: string): string => {
      if (err instanceof ApiError) {
        if (err.message === "not_enough_coins") return "Нельзя уйти в минус";
        if (err.message === "item_not_found") return "Предмет не найден";
      }
      return humanizeError(err, fallback);
    },
    [],
  );

  const fail = useCallback(
    (err: unknown, fallback: string) => {
      if (err instanceof ApiError && (err.status === 401 || err.message === "admin_unauthorized")) {
        clearAdminToken();
        router.replace("/admin/login");
        return;
      }
      setError(mapError(err, fallback));
    },
    [router, mapError],
  );

  const queryKey = `${id}|${reload}`;
  useEffect(() => {
    let alive = true;
    Promise.all([adminApi.student(id), adminApi.audit(id, 50)])
      .then(([d, a]) => {
        if (alive) setResult({ key: queryKey, detail: d, audit: a.items });
      })
      .catch((err: unknown) => {
        if (!alive) return;
        if (err instanceof ApiError && (err.status === 401 || err.message === "admin_unauthorized")) {
          clearAdminToken();
          router.replace("/admin/login");
          return;
        }
        if (err instanceof ApiError && err.message === "player_not_found") {
          setResult({ key: queryKey, notFound: true });
          return;
        }
        setResult({ key: queryKey, error: mapError(err, "Не удалось загрузить карточку участника") });
      });
    return () => {
      alive = false;
    };
  }, [id, reload, queryKey, router, mapError]);

  const load = async () => {
    setError("");
    setReload((n) => n + 1);
  };

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const confirmAndRun = (action: PendingAction) => setPending(action);

  const runPending = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      await pending.run();
      setPending(null);
      await load();
    } finally {
      setBusy(false);
    }
  };

  const loading = result?.key !== queryKey;
  const detail = result?.key === queryKey ? (result.detail ?? null) : null;
  const audit = result?.key === queryKey ? (result.audit ?? []) : [];
  const notFound = result?.key === queryKey && result.notFound === true;
  const loadError = result?.key === queryKey ? (result.error ?? "") : "";

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-[#c9a86a]/40" />
        <div className="mat-parchment h-48 animate-pulse rounded-2xl" />
        <div className="mat-parchment h-48 animate-pulse rounded-2xl" />
      </div>
    );
  }

  if (notFound || !detail) {
    return (
      <div className="mat-parchment rounded-2xl p-8 text-center">
        <p className="text-lg font-bold">{notFound ? "Участник не найден" : loadError || "Не удалось загрузить карточку"}</p>
        <Link href="/admin/students" className="mt-3 inline-block font-bold text-[#8a5412] underline">
          ← К списку участников
        </Link>
      </div>
    );
  }

  const { player, identity, consents, profile, titles, weakest_atoms, mistakes, daily_activity, counters, identities = [] } = detail;
  const activity14 = daily_activity.slice(-14);
  const maxXp = Math.max(1, ...activity14.map((d) => d.xp));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/admin/students" className="font-bold text-[#8a5412] underline">
          ← Участники
        </Link>
        <h1 className="text-2xl font-extrabold">
          {identity ? [identity.last_name, identity.first_name].filter(Boolean).join(" ") || player.display_name : player.display_name}
        </h1>
        <span className="text-sm text-[#6f5843]">#{player.id}</span>
      </div>

      {error && (
        <p role="alert" className="rounded-xl bg-[#ffe9e6] px-4 py-3 font-bold text-[#a82f25]">
          {error}
        </p>
      )}
      {toast && (
        <p role="status" className="rounded-xl bg-[#e2f6f2] px-4 py-3 font-bold text-[#17685b]">
          {toast}
        </p>
      )}

      <IdentitySection
        identity={identity}
        onSave={async (patch, reason) => {
          try {
            await adminApi.patchIdentity(id, patch, reason);
            setToast("Анкета сохранена");
            await load();
          } catch (err) {
            fail(err, "Не удалось сохранить анкету");
          }
        }}
      />

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Мессенджеры</h2>
        {identities.length === 0 ? (
          <p className="mt-2 text-sm text-[#6f5843]">Привязок нет — участник ещё не входил через Telegram/MAX</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {identities.map((m) => (
              <li key={`${m.provider}-${m.provider_user_id}`} className="flex flex-wrap gap-x-3">
                <span className="font-bold">{m.provider === "telegram" ? "Telegram" : m.provider === "max" ? "MAX" : m.provider}</span>
                <span>{m.display_name}</span>
                <span className="text-[#6f5843]">id {m.provider_user_id}</span>
                <span className="ml-auto text-[#6f5843]">{fmtDateTime(m.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Согласия</h2>
        {consents.length === 0 ? (
          <p className="mt-2 text-sm text-[#6f5843]">Согласий нет</p>
        ) : (
          <table className="mt-2 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#c9a86a] text-xs uppercase text-[#6f5843]">
                <th className="py-2 pr-3">Тип</th>
                <th className="py-2 pr-3">Версия</th>
                <th className="py-2">Дата</th>
              </tr>
            </thead>
            <tbody>
              {consents.map((c, i) => (
                <tr key={`${c.type}-${i}`} className="border-b border-[#c9a86a]/40">
                  <td className="py-2 pr-3">{c.type}</td>
                  <td className="py-2 pr-3">{c.version}</td>
                  <td className="py-2">{fmtDateTime(c.accepted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Прогресс</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Stat label="Уровень" value={String(player.level)} />
          <Stat label="XP" value={String(player.xp)} />
          <Stat label="Монеты" value={String(player.coins)} />
          <Stat label="Серия" value={`${player.streak_days} дн.`} />
          <Stat label="Сердца" value={player.hearts != null ? String(player.hearts) : "—"} />
          <Stat label="Книга" value={profile?.book_id ?? "—"} />
          <Stat label="Модуль" value={profile?.module_id ?? "—"} />
          <Stat label="Цель XP/день" value={profile?.daily_goal_xp != null ? String(profile.daily_goal_xp) : "—"} />
          <Stat label="Предметы" value={String(counters.inventory)} />
          <Stat label="Замок" value={String(counters.castle_owned)} />
          <Stat label="Сессии" value={String(counters.sessions_total)} />
        </div>
        <h3 className="mt-4 text-sm font-bold text-[#6f5843]">Активность за 14 дней</h3>
        {activity14.length === 0 ? (
          <p className="mt-1 text-sm text-[#6f5843]">Нет данных</p>
        ) : (
          <div className="mt-2 flex items-end gap-1" role="img" aria-label="Диаграмма активности за 14 дней">
            {activity14.map((d) => (
              <div key={d.day} className="flex flex-1 flex-col items-center gap-1" title={`${fmtDate(d.day)}: ${d.xp} XP, ${d.sessions} сессий`}>
                <div
                  className="w-full rounded-t bg-[#c98a22]"
                  style={{ height: `${Math.max(3, Math.round((d.xp / maxXp) * 48))}px` }}
                />
                <div className="w-full truncate text-center text-[9px] text-[#6f5843]">{d.day.slice(5)}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Звания</h2>
        {titles.length === 0 ? (
          <p className="mt-2 text-sm text-[#6f5843]">Званий нет</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {titles.map((t) => (
              <li key={t.track} className="flex flex-wrap gap-x-3">
                <span className="font-bold">{t.title_ru ?? t.track}</span>
                <span className="text-[#6f5843]">ур. {t.level}</span>
                {t.worn && <span className="font-bold text-[#17685b]">носится</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <WeakAtomsSection
        atoms={weakest_atoms}
        onAction={(atomId, action, reason) =>
          confirmAndRun({
            title: action === "master" ? "Отметить слово выученным?" : "Сбросить прогресс слова?",
            body: `${atomId} · причина: ${reason}`,
            run: async () => {
              try {
                await adminApi.mastery(id, atomId, action, reason);
                setToast(action === "master" ? "Слово отмечено выученным" : "Прогресс слова сброшен");
              } catch (err) {
                fail(err, "Не удалось изменить слово");
              }
            },
          })
        }
      />

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Ошибки</h2>
        {mistakes.length === 0 ? (
          <p className="mt-2 text-sm text-[#6f5843]">Ошибок нет</p>
        ) : (
          <ul className="mt-2 space-y-1 text-sm">
            {mistakes.map((m, i) => (
              <li key={`${m.unit_id}-${i}`}>
                <span className="font-bold">{m.item}</span> <span className="text-[#6f5843]">({m.unit_id})</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ActionsSection
        onAdjust={(kind, delta, reason) =>
          confirmAndRun({
            title: `${delta >= 0 ? "Начислить" : "Списать"} ${Math.abs(delta)} ${kind === "coins" ? "монет" : "XP"}?`,
            body: `Причина: ${reason}`,
            run: async () => {
              try {
                await adminApi.adjust(id, kind, delta, reason);
                setToast("Баланс обновлён");
              } catch (err) {
                fail(err, "Не удалось изменить баланс");
              }
            },
          })
        }
        onItem={(itemId, action, reason) =>
          confirmAndRun({
            title: action === "grant" ? "Выдать предмет?" : "Отозвать предмет?",
            body: `${itemId} · причина: ${reason}`,
            run: async () => {
              try {
                await adminApi.items(id, itemId, action, reason);
                setToast(action === "grant" ? "Предмет выдан" : "Предмет отозван");
              } catch (err) {
                fail(err, "Не удалось изменить предметы");
              }
            },
          })
        }
      />

      <section className="mat-parchment rounded-2xl p-5">
        <h2 className="text-lg font-extrabold">Журнал</h2>
        {audit.length === 0 ? (
          <p className="mt-2 text-sm text-[#6f5843]">Записей нет</p>
        ) : (
          <ul className="mt-2 space-y-2 text-sm">
            {audit.map((a, i) => (
              <li key={i} className="border-b border-[#c9a86a]/40 pb-2">
                <div className="flex flex-wrap gap-x-3">
                  <span className="font-bold">{a.action}</span>
                  <span className="text-[#6f5843]">{a.entity}</span>
                  <span className="text-[#6f5843]">{a.actor}</span>
                  <span className="ml-auto text-[#6f5843]">{fmtDateTime(a.created_at)}</span>
                </div>
                {a.payload != null && (
                  <pre className="mt-1 overflow-x-auto rounded bg-[#3b2a1e]/5 p-2 text-xs">
                    {typeof a.payload === "string" ? a.payload : JSON.stringify(a.payload, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {pending && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
          onClick={() => !busy && setPending(null)}
        >
          <div className="mat-parchment w-full max-w-sm rounded-2xl p-5" onClick={(e) => e.stopPropagation()}>
            <h2 id="confirm-title" className="text-lg font-extrabold">
              {pending.title}
            </h2>
            <p className="mt-2 text-sm text-[#6f5843]">{pending.body}</p>
            <div className="mt-5 flex gap-3">
              <Button size="md" onClick={runPending} disabled={busy}>
                {busy ? "Выполняем…" : "Подтвердить"}
              </Button>
              <Button size="md" variant="paper" onClick={() => setPending(null)} disabled={busy}>
                Отмена
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="mat-enamel rounded-xl px-3 py-2">
      <div className="text-xs text-[#6f5843]">{label}</div>
      <div className="font-extrabold tabular-nums">{value}</div>
    </div>
  );
}

const inputCls =
  "mt-1 min-h-11 w-full rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]";

function IdentitySection({
  identity,
  onSave,
}: {
  identity: AdminStudentDetail["identity"];
  onSave: (patch: IdentityPatch, reason: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    first_name: identity?.first_name ?? "",
    last_name: identity?.last_name ?? "",
    birth_date: identity?.birth_date ?? "",
    school_number: identity?.school_number ?? "",
    class_grade: identity?.class_grade != null ? String(identity.class_grade) : "",
    class_letter: identity?.class_letter ?? "",
    parent_email: identity?.parent_email ?? "",
  });
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const field = (key: keyof typeof form, label: string, type = "text") => (
    <div>
      <label htmlFor={`id-${key}`} className="text-sm font-bold">
        {label}
      </label>
      <input
        id={`id-${key}`}
        type={type}
        value={form[key]}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        className={inputCls}
      />
    </div>
  );

  return (
    <section className="mat-parchment rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-extrabold">Анкета</h2>
        {!editing && (
          <Button size="md" variant="paper" onClick={() => setEditing(true)}>
            Редактировать
          </Button>
        )}
      </div>
      {!identity && !editing && <p className="mt-2 text-sm text-[#6f5843]">Анкета не заполнена</p>}

      {!editing && identity && (
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Row k="Имя" v={identity.first_name} />
          <Row k="Фамилия" v={identity.last_name} />
          <Row k="Дата рождения" v={fmtDate(identity.birth_date)} />
          <Row k="Школа" v={identity.school_number} />
          <Row
            k="Класс"
            v={identity.class_grade != null ? `${identity.class_grade}${identity.class_letter ?? ""}` : null}
          />
          <Row k="Email родителя" v={identity.parent_email} />
          <Row k="Телефон родителя" v={identity.parent_phone_masked} />
          <Row k="Телефон подтверждён" v={identity.phone_verified ? "да" : "нет"} />
        </dl>
      )}

      {editing && (
        <form
          className="mt-3"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!reason.trim() || saving) return;
            setSaving(true);
            const patch: IdentityPatch = {};
            if (form.first_name.trim()) patch.first_name = form.first_name.trim();
            if (form.last_name.trim()) patch.last_name = form.last_name.trim();
            if (form.birth_date) patch.birth_date = form.birth_date;
            if (form.school_number.trim()) patch.school_number = form.school_number.trim();
            if (form.class_grade) patch.class_grade = Number(form.class_grade);
            if (form.class_letter.trim()) patch.class_letter = form.class_letter.trim();
            if (form.parent_email.trim()) patch.parent_email = form.parent_email.trim();
            await onSave(patch, reason.trim());
            setSaving(false);
            setEditing(false);
          }}
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {field("first_name", "Имя")}
            {field("last_name", "Фамилия")}
            {field("birth_date", "Дата рождения", "date")}
            {field("school_number", "Школа")}
            {field("class_grade", "Класс", "number")}
            {field("class_letter", "Буква класса")}
            {field("parent_email", "Email родителя", "email")}
          </div>
          <p className="mt-3 text-xs text-[#6f5843]">Смена телефона выполняется отдельно и сбрасывает верификацию.</p>
          <div className="mt-3">
            <label htmlFor="id-reason" className="text-sm font-bold">
              Причина правки (обязательно)
            </label>
            <input
              id="id-reason"
              type="text"
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Например: просьба родителя от 12.09"
              className={inputCls}
            />
          </div>
          <div className="mt-4 flex gap-3">
            <Button size="md" type="submit" disabled={!reason.trim() || saving}>
              {saving ? "Сохраняем…" : "Сохранить"}
            </Button>
            <Button size="md" variant="paper" onClick={() => setEditing(false)} disabled={saving}>
              Отмена
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function Row({ k, v }: { k: string; v: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-40 shrink-0 text-[#6f5843]">{k}</dt>
      <dd className="font-bold">{v ?? "—"}</dd>
    </div>
  );
}

function WeakAtomsSection({
  atoms,
  onAction,
}: {
  atoms: AdminStudentDetail["weakest_atoms"];
  onAction: (atomId: string, action: "reset" | "master", reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <section className="mat-parchment rounded-2xl p-5">
      <h2 className="text-lg font-extrabold">Слабые слова</h2>
      <div className="mt-3">
        <label htmlFor="atoms-reason" className="text-sm font-bold">
          Причина (обязательно для действий)
        </label>
        <input
          id="atoms-reason"
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: слово пройдено на уроке"
          className={inputCls}
        />
      </div>
      {atoms.length === 0 ? (
        <p className="mt-2 text-sm text-[#6f5843]">Слабых слов нет</p>
      ) : (
        <ul className="mt-3 space-y-2 text-sm">
          {atoms.map((a) => (
            <li key={a.atom_id} className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-[#c9a86a]/40 pb-2">
              <span className="font-bold">{a.atom_id}</span>
              <span className="text-[#6f5843]">прочность {a.strength}</span>
              <span className="text-[#6f5843]">ошибок {a.wrong_count}</span>
              <span className="ml-auto flex gap-2">
                <Button size="md" variant="paper" disabled={!reason.trim()} onClick={() => onAction(a.atom_id, "master", reason.trim())}>
                  Выучено
                </Button>
                <Button size="md" variant="paper" disabled={!reason.trim()} onClick={() => onAction(a.atom_id, "reset", reason.trim())}>
                  Сброс
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ActionsSection({
  onAdjust,
  onItem,
}: {
  onAdjust: (kind: "coins" | "xp", delta: number, reason: string) => void;
  onItem: (itemId: string, action: "grant" | "revoke", reason: string) => void;
}) {
  const [kind, setKind] = useState<"coins" | "xp">("coins");
  const [delta, setDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const [itemId, setItemId] = useState("");
  const [itemReason, setItemReason] = useState("");

  const deltaNum = Number(delta);
  const deltaValid = Number.isFinite(deltaNum) && deltaNum !== 0;

  return (
    <section className="mat-parchment rounded-2xl p-5">
      <h2 className="text-lg font-extrabold">Действия</h2>

      <div className="mt-3 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-bold text-[#6f5843]">Корректировка баланса</h3>
          <div className="mt-2 flex gap-2">
            <select
              aria-label="Что меняем"
              value={kind}
              onChange={(e) => setKind(e.target.value as "coins" | "xp")}
              className="min-h-11 rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 outline-none focus:border-[#8a5412]"
            >
              <option value="coins">Монеты</option>
              <option value="xp">XP</option>
            </select>
            <input
              aria-label="Сумма (можно с минусом)"
              type="number"
              value={delta}
              onChange={(e) => setDelta(e.target.value)}
              placeholder="±сумма"
              className={inputCls}
            />
          </div>
          <input
            aria-label="Причина корректировки"
            type="text"
            value={adjustReason}
            onChange={(e) => setAdjustReason(e.target.value)}
            placeholder="Причина (обязательно)"
            className={inputCls}
          />
          <Button
            size="md"
            className="mt-3"
            disabled={!deltaValid || !adjustReason.trim()}
            onClick={() => onAdjust(kind, deltaNum, adjustReason.trim())}
          >
            Применить
          </Button>
        </div>

        <div>
          <h3 className="text-sm font-bold text-[#6f5843]">Предмет</h3>
          <input
            aria-label="ID предмета"
            type="text"
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
            placeholder="item_id"
            className={inputCls}
          />
          <input
            aria-label="Причина выдачи или отзыва"
            type="text"
            value={itemReason}
            onChange={(e) => setItemReason(e.target.value)}
            placeholder="Причина (обязательно)"
            className={inputCls}
          />
          <div className="mt-3 flex gap-2">
            <Button
              size="md"
              disabled={!itemId.trim() || !itemReason.trim()}
              onClick={() => onItem(itemId.trim(), "grant", itemReason.trim())}
            >
              Выдать
            </Button>
            <Button
              size="md"
              variant="paper"
              disabled={!itemId.trim() || !itemReason.trim()}
              onClick={() => onItem(itemId.trim(), "revoke", itemReason.trim())}
            >
              Отозвать
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
