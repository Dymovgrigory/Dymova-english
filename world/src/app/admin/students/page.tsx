"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { adminApi, type AdminStudentList, type AdminStudentRow } from "@/lib/v2/admin";
import { humanizeError } from "@/lib/api";
import { Button } from "@/design/Button";

const PER_PAGE = 20;

function fullName(row: AdminStudentRow): string {
  const fio = [row.last_name, row.first_name].filter(Boolean).join(" ").trim();
  return fio || row.display_name;
}

function fmtDay(day: string | null): string {
  if (!day) return "—";
  const d = new Date(day);
  return Number.isNaN(d.getTime()) ? day : d.toLocaleDateString("ru-RU");
}

export default function AdminStudentsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [classGrade, setClassGrade] = useState<number | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [page, setPage] = useState(1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setQDebounced(q.trim());
      setPage(1);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q]);

  const queryKey = `${qDebounced}|${classGrade ?? ""}|${verified ?? ""}|${page}`;
  type Result = { key: string; data?: AdminStudentList; error?: string };
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    let alive = true;
    adminApi
      .students({
        q: qDebounced || undefined,
        class_grade: classGrade ?? undefined,
        verified: verified ?? undefined,
        page,
        per_page: PER_PAGE,
      })
      .then((data) => {
        if (alive) setResult({ key: queryKey, data });
      })
      .catch((err) => {
        if (alive) setResult({ key: queryKey, error: humanizeError(err, "Не удалось загрузить список участников") });
      });
    return () => {
      alive = false;
    };
  }, [qDebounced, classGrade, verified, page, queryKey]);

  const loading = result?.key !== queryKey;
  const data = result?.key === queryKey ? (result.data ?? null) : null;
  const error = result?.key === queryKey ? (result.error ?? "") : "";

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  const rowMain = (row: AdminStudentRow) => (
    <>
      <div className="font-bold">{fullName(row)}</div>
      {fullName(row) !== row.display_name && <div className="text-xs text-[#6f5843]">{row.display_name}</div>}
    </>
  );

  const rowStats = (row: AdminStudentRow) => (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[#6f5843]">
      <span>Школа {row.school_number ?? "—"}</span>
      <span>{row.class_grade != null ? `${row.class_grade} класс` : "—"}</span>
      <span>{row.phone_masked ?? "—"} {row.phone_verified ? "✓" : ""}</span>
      <span>XP {row.xp}</span>
      <span>Монеты {row.coins}</span>
      <span>Серия {row.streak_days}</span>
      <span>Активность: {fmtDay(row.last_active_day)}</span>
    </div>
  );

  return (
    <div>
      <h1 className="text-2xl font-extrabold">Участники</h1>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <label htmlFor="students-q" className="text-sm font-bold">
            Поиск
          </label>
          <input
            id="students-q"
            type="search"
            placeholder="ФИО, ник, телефон…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="mt-1 min-h-11 w-full rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]"
          />
        </div>
        <div>
          <label htmlFor="students-class" className="text-sm font-bold">
            Класс
          </label>
          <select
            id="students-class"
            value={classGrade ?? ""}
            onChange={(e) => {
              setClassGrade(e.target.value ? Number(e.target.value) : null);
              setPage(1);
            }}
            className="mt-1 min-h-11 rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]"
          >
            <option value="">Все</option>
            {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="students-verified" className="text-sm font-bold">
            Телефон
          </label>
          <select
            id="students-verified"
            value={verified == null ? "" : verified ? "true" : "false"}
            onChange={(e) => {
              setVerified(e.target.value === "" ? null : e.target.value === "true");
              setPage(1);
            }}
            className="mt-1 min-h-11 rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]"
          >
            <option value="">Все</option>
            <option value="true">Подтверждён</option>
            <option value="false">Не подтверждён</option>
          </select>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-xl bg-[#ffe9e6] px-4 py-3 font-bold text-[#a82f25]">
          {error}
        </p>
      )}

      {/* Мобильные карточки */}
      <div className="mt-4 space-y-3 sm:hidden">
        {loading &&
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="mat-enamel h-24 animate-pulse rounded-2xl" aria-hidden="true" />
          ))}
        {!loading &&
          data?.items.map((row) => (
            <button
              key={row.player_id}
              type="button"
              onClick={() => router.push(`/admin/students/${row.player_id}`)}
              className="mat-enamel press block w-full rounded-2xl p-4 text-left"
            >
              {rowMain(row)}
              {rowStats(row)}
            </button>
          ))}
        {!loading && data && data.items.length === 0 && (
          <div className="mat-enamel rounded-2xl p-6 text-center text-[#6f5843]">По этим фильтрам никого не нашлось</div>
        )}
      </div>

      {/* Таблица на десктопе */}
      <div className="mat-parchment mt-4 hidden overflow-x-auto rounded-2xl sm:block">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead>
            <tr className="border-b-2 border-[#c9a86a] text-xs uppercase tracking-wide text-[#6f5843]">
              <th className="px-3 py-3">Участник</th>
              <th className="px-3 py-3">Школа</th>
              <th className="px-3 py-3">Класс</th>
              <th className="px-3 py-3">Телефон</th>
              <th className="px-3 py-3" aria-label="Телефон подтверждён">✓</th>
              <th className="px-3 py-3 text-right">XP</th>
              <th className="px-3 py-3 text-right">Монеты</th>
              <th className="px-3 py-3 text-right">Серия</th>
              <th className="px-3 py-3">Активность</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} aria-hidden="true">
                  {Array.from({ length: 9 }).map((_, j) => (
                    <td key={j} className="px-3 py-3">
                      <div className="h-4 animate-pulse rounded bg-[#c9a86a]/40" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              data?.items.map((row) => (
                <tr
                  key={row.player_id}
                  onClick={() => router.push(`/admin/students/${row.player_id}`)}
                  className="cursor-pointer border-b border-[#c9a86a]/40 transition-colors hover:bg-[#fffaf0]/70"
                >
                  <td className="px-3 py-3">{rowMain(row)}</td>
                  <td className="px-3 py-3">{row.school_number ?? "—"}</td>
                  <td className="px-3 py-3">{row.class_grade ?? "—"}</td>
                  <td className="px-3 py-3">{row.phone_masked ?? "—"}</td>
                  <td className="px-3 py-3" aria-label={row.phone_verified ? "подтверждён" : "не подтверждён"}>
                    {row.phone_verified ? "✓" : "—"}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.xp}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.coins}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.streak_days}</td>
                  <td className="px-3 py-3">{fmtDay(row.last_active_day)}</td>
                </tr>
              ))}
          </tbody>
        </table>
        {!loading && data && data.items.length === 0 && (
          <div className="p-6 text-center text-[#6f5843]">По этим фильтрам никого не нашлось</div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="text-sm text-[#6f5843]">Всего {data?.total ?? "…"}</div>
        <div className="flex items-center gap-2">
          <Button variant="paper" size="md" disabled={loading || page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Назад
          </Button>
          <span className="text-sm font-bold tabular-nums">
            {page} / {totalPages}
          </span>
          <Button
            variant="paper"
            size="md"
            disabled={loading || page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Вперёд →
          </Button>
        </div>
      </div>
    </div>
  );
}
