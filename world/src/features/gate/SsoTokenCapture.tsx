"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { rememberPlayerToken } from "@/lib/token";
import { rememberFromLk } from "./BackToLk";

/**
 * SSO из личного кабинета: ЛК открывает Мир со ссылкой
 * `/?world_token=wses.<id>.<secret>&world_key=<external_key>`.
 * Принимаем токен, кладём в localStorage и сразу чистим URL —
 * ссылка с секретом не должна остаться в истории/реферах.
 */
export function SsoTokenCapture() {
  const params = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (params.get("from") === "lk") rememberFromLk();
    const token = params.get("world_token");
    if (!token) return;
    rememberPlayerToken(token, params.get("world_key") || undefined);
    const url = new URL(window.location.href);
    url.searchParams.delete("world_token");
    url.searchParams.delete("world_key");
    url.searchParams.delete("from");
    router.replace(url.pathname + url.search);
  }, [params, router]);

  return null;
}
