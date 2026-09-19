import Link from "next/link";
import type { ReactNode } from "react";

import { LEGAL_VERSION, OPERATOR_EMAIL, OPERATOR_NAME } from "@/lib/legal";

export function LegalDoc({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="min-h-dvh px-4 py-10">
      <article className="mat-parchment mx-auto max-w-2xl rounded-3xl p-6 sm:p-10">
        <h1 className="font-fairy text-[30px] font-black leading-9 text-ink">{title}</h1>
        <p className="mt-2 text-[14px] font-bold text-ink-soft">
          Редакция от {LEGAL_VERSION} · Оператор: {OPERATOR_NAME}
        </p>
        <div className="mt-6 flex flex-col gap-4 text-[16px] font-semibold leading-7 text-ink [&_h2]:mt-4 [&_h2]:font-fairy [&_h2]:text-[20px] [&_h2]:font-black [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
        <p className="mt-8 border-t border-[#cdb58a] pt-4 text-[14px] font-semibold text-ink-soft">
          Вопросы и отзыв согласия:{" "}
          <a href={`mailto:${OPERATOR_EMAIL}`} className="font-bold text-ink underline">
            {OPERATOR_EMAIL}
          </a>
        </p>
        <Link
          href="/"
          className="mat-enamel press mt-6 inline-flex min-h-11 items-center rounded-2xl px-5 text-[15px] font-extrabold text-ink"
        >
          ← Вернуться в Фоксинбург
        </Link>
      </article>
    </main>
  );
}
