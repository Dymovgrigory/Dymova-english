/** Версия юридических текстов Foxinburg World. Меняется вместе с текстами страниц /legal. */
export const LEGAL_VERSION = "2026-09-19";

export const OPERATOR_NAME = "Дымова Вероника Александровна";
export const OPERATOR_EMAIL = "vkrivobokova4@gmail.com";

export type ConsentType = "pd_child" | "privacy" | "marketing";

/** Краткие формулировки у чекбоксов регистрации. Полные тексты — на страницах /legal. */
export const CONSENT_LABELS: Record<ConsentType, string> = {
  pd_child:
    "Я являюсь родителем/законным представителем ребёнка и даю согласие на обработку его персональных данных",
  privacy: "Принимаю политику конфиденциальности",
  marketing: "Хочу получать новости и акции школы (необязательно)",
};

export const CONSENT_LINKS: Partial<Record<ConsentType, string>> = {
  pd_child: "/legal/pd-consent",
  privacy: "/legal/privacy",
};
