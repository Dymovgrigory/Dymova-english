"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { adminApi } from "@/lib/v2/admin";
import { Button } from "@/design/Button";

function loginError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.message === "invalid_credentials") return "Неверный логин или пароль";
    if (err.message === "too_many_attempts") return "Слишком много попыток, подождите минуту";
    if (err.status === 401) return "Неверный логин или пароль";
  }
  return "Не удалось войти. Попробуйте ещё раз";
}

export default function AdminLoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      await adminApi.login(login.trim(), password);
      router.replace("/admin/students");
    } catch (err) {
      setError(loginError(err));
      setLoading(false);
    }
  };

  return (
    <div className="study-plain flex min-h-dvh items-center justify-center px-4">
      <form onSubmit={submit} className="mat-parchment w-full max-w-sm rounded-3xl p-6" aria-label="Вход в админ-панель">
        <h1 className="text-xl font-extrabold">Foxinburg World — Админ</h1>
        <p className="mt-1 text-sm text-[#6f5843]">Вход для администраторов</p>

        <label className="mt-5 block text-sm font-bold" htmlFor="admin-login">
          Логин
        </label>
        <input
          id="admin-login"
          type="text"
          autoComplete="username"
          required
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          className="mt-1 min-h-11 w-full rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]"
        />

        <label className="mt-4 block text-sm font-bold" htmlFor="admin-password">
          Пароль
        </label>
        <input
          id="admin-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 min-h-11 w-full rounded-xl border-2 border-[#c9a86a] bg-[#fffaf0] px-3 text-base outline-none focus:border-[#8a5412]"
        />

        {error && (
          <p role="alert" className="mt-4 rounded-xl bg-[#ffe9e6] px-3 py-2 text-sm font-bold text-[#a82f25]">
            {error}
          </p>
        )}

        <Button type="submit" block className="mt-6" disabled={loading || !login.trim() || !password}>
          {loading ? "Входим…" : "Войти"}
        </Button>
      </form>
    </div>
  );
}
