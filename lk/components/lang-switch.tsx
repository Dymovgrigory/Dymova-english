"use client";

import { Lang, useI18n } from "@/lib/i18n";

// Переключатель RU/EN — ставится в шапку каждой страницы и на экраны входа.
export default function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  const options: Lang[] = ["ru", "en"];
  return (
    <div className="lang-switch" role="group" aria-label={t.common.langLabel}>
      {options.map((l) => (
        <button
          key={l}
          type="button"
          className={"lang-chip" + (lang === l ? " lang-chip-active" : "")}
          aria-pressed={lang === l}
          onClick={() => setLang(l)}
        >
          {l === "ru" ? t.common.ru : t.common.en}
        </button>
      ))}
    </div>
  );
}
