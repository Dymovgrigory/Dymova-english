"use client";

// Двуязычие ЛК (ТЗ §6: русский + английский).
// Язык хранится в localStorage (`lk_lang`), по умолчанию — русский.
// Все компоненты ЛК — клиентские, поэтому провайдер монтируется в layout
// через client-обёртку; гидратация безопасна: сервер и первый рендер — RU,
// локальное значение подхватывается в эффекте после монтирования.

import { createContext, useContext, useEffect, useState } from "react";

export type Lang = "ru" | "en";

export const LANG_KEY = "lk_lang";
export const DEFAULT_LANG: Lang = "ru";

const RU = {
  common: {
    brand: "Фоксинбург",
    lkBadge: "Личный кабинет",
    logout: "Выйти",
    loadingCabinet: "Загружаем кабинет…",
    loadingProgress: "Загружаем прогресс…",
    loadingSchedule: "Загружаем расписание…",
    profilesAria: "Профили детей",
    back: "← Назад",
    ru: "RU",
    en: "EN",
    langLabel: "Язык интерфейса",
  },
  auth: {
    title: "Личный кабинет",
    sub: "Школа Фоксинбург: расписание, прогресс ребёнка, тренажёр слов и Мир Фоксинбурга. Вход — по номеру телефона, который указан в договоре.",
    phoneLabel: "Номер телефона",
    nameLabel: "Ваше имя",
    namePlaceholder: "Как к вам обращаться",
    consentPd: "Согласен(на) на обработку персональных данных моего ребёнка",
    consentPrivacy: "Принимаю",
    privacyLink: "политику конфиденциальности",
    submit: "Войти",
    submitting: "Отправляем…",
    note: "Подтверждение номера — бесплатно, через ботов Max или Telegram. SMS не требуется. Если номер в договоре отличается — свяжитесь с администратором школы.",
    errIncompletePhone: "Введите номер телефона полностью.",
    errEmptyName: "Введите ваше имя.",
    errNeedConsents: "Для регистрации нужны оба согласия.",
    recently_sent: "Мы уже отправили запрос на этот номер. Подтвердите его в боте — и нажмите «Проверить».",
    daily_limit: "Слишком много попыток за сегодня. Попробуйте завтра или напишите нам в Max.",
    consent_required: "Нужно согласие на обработку персональных данных.",
    generic: "Не получилось отправить. Попробуйте ещё раз или напишите нам в Max.",
  },
  confirm: {
    title: "Подтвердите номер",
    sub: "Номер подтверждается одной кнопкой в боте — без SMS и звонков.",
    step1: "Нажмите одну из кнопок ниже и откройте диалог с ботом.",
    step2: "В боте поделитесь номером телефона кнопкой «Поделиться контактом».",
    step3: "Вернитесь сюда — подтверждение подтянется автоматически.",
    botMax: "Написать в Max",
    botTg: "Открыть Telegram-бота",
    check: "Проверить подтверждение",
    checking: "Проверяю…",
    note: "Проверяем автоматически каждые несколько секунд — можно просто оставить страницу открытой.",
    noticeUnconfirmed: "Пока не вижу подтверждения: откройте бота и поделитесь номером телефона кнопкой «Поделиться контактом», затем нажмите «Проверить» ещё раз.",
    noticeMany: "Слишком много попыток. Подождите минуту и попробуйте снова.",
    noticeBot: "Не смог связаться с ботом. Попробуйте через полминуты.",
    noticeGeneric: "Что-то пошло не так. Попробуйте ещё раз.",
  },
  dashboard: {
    title: "Дашборд",
    sub: "{name} — общая картина занятий и прогресса",
    profileFallback: "Профиль",
    groups: "Группы",
    guestBanner: "Номер пока не привязан к договору — включён гостевой доступ: Мир, тренажёр слов и рейтинги. Чтобы видеть расписание и прогресс, свяжитесь с администратором школы.",
    scheduleTitle: "Расписание и посещаемость",
    scheduleBody: "Занятия по неделям и отметки посещаемости — данные синхронизируются с CRM автоматически.",
    scheduleLink: "Открыть расписание →",
    wordsTitle: "Тренажёр слов",
    wordsBody: "Словари Spotlight, My Level, Get Involved, Super Minds и уровневые наборы от Pre-A1 с картинками и озвучкой.",
    wordsLink: "Открыть тренажёр →",
    worldTitle: "Мир Фоксинбурга",
    worldBody: "Замок, башня Spotlight и лиги: прогресс ребёнка и вход без пароля.",
    worldLink: "Открыть раздел Мира →",
    achTitle: "Достижения",
    achBody: "Рейтинги, серии занятий и награды появятся вместе с игровым прогрессом.",
    tagDone: "Готово",
    tagSoon: "Скоро",
  },
  schedule: {
    title: "Расписание",
    sub: "{name} · занятия и посещаемость из CRM (обновляется автоматически)",
    weekBack: "← Неделя назад",
    weekCurrent: "Текущая неделя",
    weekFwd: "Неделя вперёд →",
    loadError: "Не удалось загрузить расписание. Попробуйте обновить страницу.",
    empty: "На этой неделе занятий нет. Переключите профиль ребёнка или посмотрите соседние недели.",
    today: "сегодня",
    visited: "✓ был",
    missed: "пропуск",
    unknown: "нет отметки",
    wd: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
    months: [
      "января", "февраля", "марта", "апреля", "мая", "июня",
      "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ],
  },
  words: {
    title: "Тренажёр слов",
    sub: "{name} · словари по уровням и учебникам",
    learned: "выучено слов",
    dueToday: "к повторению сегодня",
    accuracy: "точность ответов",
    loadError: "Не удалось загрузить словари. Попробуйте обновить страницу.",
    empty: "Словари появятся здесь — публичные уровневые наборы и наборы, назначенные педагогом вашей группе.",
    kindLevel: "Уровень",
    kindBook: "Учебник",
    kindTopic: "Тема",
    setProgress: "{learned}/{total} · к повтору {due}",
    train: "Тренировать →",
  },
  train: {
    loading: "Собираем тренировку…",
    back: "← Словари",
    backToSets: "← Назад к словарям",
    speakTitle: "Озвучить",
    promptInput: "Напишите слово для перевода:",
    check: "Проверить",
    correct: "Верно!",
    wrong: "Правильный ответ:",
    listen: "🔊 Послушать слово",
    finish: "Завершить",
    next: "Дальше →",
    startError: "Не удалось начать тренировку. Попробуйте ещё раз.",
    doneTitle: "Готово!",
    doneSub: "{correct} из {all} верно{pct}. Слова, в которых были ошибки, вернутся в тренировку уже сегодня.",
    again: "Ещё раз",
    toSets: "← К словарям",
  },
  world: {
    title: "Мир Фоксинбурга",
    sub: "{name} · замок, башни Spotlight и лиги",
    level: "уровень",
    xp: "очков опыта",
    coins: "монет",
    streak: "дней подряд",
    towers: "Башни Мира",
    towerSpotlight: "Башня Spotlight",
    towerLevel: "уровень {level}",
    league: "Лига недели",
    leagueBody: "Место {rank} · {xp} XP за неделю",
    notStartedTitle: "Путешествие ещё не началось",
    notStartedSub: "{name} пока не был в Мире Фоксинбурга. Войдите — замок, башня Spotlight и первая лига ждут!",
    enterSubLinked: "Вход без пароля — личный кабинет сам откроет Мир за {name}.",
    enter: "Войти в Мир Фоксинбурга",
    entering: "Открываем Мир…",
    loadError: "Не удалось загрузить прогресс Мира. Попробуйте обновить страницу.",
    enterError: "Не удалось войти в Мир. Попробуйте ещё раз.",
  },
};

export type Dict = typeof RU;

const EN: Dict = {
  common: {
    brand: "Foxinburg",
    lkBadge: "Personal account",
    logout: "Sign out",
    loadingCabinet: "Loading your account…",
    loadingProgress: "Loading progress…",
    loadingSchedule: "Loading schedule…",
    profilesAria: "Children profiles",
    back: "← Back",
    ru: "RU",
    en: "EN",
    langLabel: "Interface language",
  },
  auth: {
    title: "Personal account",
    sub: "Foxinburg school: schedule, your child's progress, word trainer and the Foxinburg World. Sign in with the phone number from your contract.",
    phoneLabel: "Phone number",
    nameLabel: "Your name",
    namePlaceholder: "How should we address you",
    consentPd: "I consent to the processing of my child's personal data",
    consentPrivacy: "I accept the",
    privacyLink: "privacy policy",
    submit: "Sign in",
    submitting: "Sending…",
    note: "Phone confirmation is free — via Max or Telegram bots. No SMS needed. If the contract number differs, contact the school administrator.",
    errIncompletePhone: "Please enter the full phone number.",
    errEmptyName: "Please enter your name.",
    errNeedConsents: "Both consents are required to register.",
    recently_sent: "We have already sent a request to this number. Confirm it in the bot — then press «Check».",
    daily_limit: "Too many attempts today. Try tomorrow or message us in Max.",
    consent_required: "Consent to personal data processing is required.",
    generic: "Could not send. Try again or message us in Max.",
  },
  confirm: {
    title: "Confirm your number",
    sub: "Confirm with a single button in the bot — no SMS or calls.",
    step1: "Press one of the buttons below and open the bot chat.",
    step2: "Share your phone number in the bot using the «Share contact» button.",
    step3: "Come back here — the confirmation will be picked up automatically.",
    botMax: "Message in Max",
    botTg: "Open Telegram bot",
    check: "Check confirmation",
    checking: "Checking…",
    note: "We check automatically every few seconds — you can just leave this page open.",
    noticeUnconfirmed: "No confirmation yet: open the bot and share your phone number with the «Share contact» button, then press «Check» again.",
    noticeMany: "Too many attempts. Wait a minute and try again.",
    noticeBot: "Could not reach the bot. Try again in half a minute.",
    noticeGeneric: "Something went wrong. Please try again.",
  },
  dashboard: {
    title: "Dashboard",
    sub: "{name} — the big picture of classes and progress",
    profileFallback: "Profile",
    groups: "Groups",
    guestBanner: "This number is not linked to a contract yet — guest access is on: the World, word trainer and ratings. To see the schedule and progress, contact the school administrator.",
    scheduleTitle: "Schedule and attendance",
    scheduleBody: "Weekly classes and attendance marks — data is synced with the CRM automatically.",
    scheduleLink: "Open schedule →",
    wordsTitle: "Word trainer",
    wordsBody: "Spotlight, My Level, Get Involved, Super Minds word lists and level-based sets from Pre-A1 with pictures and audio.",
    wordsLink: "Open trainer →",
    worldTitle: "Foxinburg World",
    worldBody: "Castle, Spotlight tower and leagues: your child's progress and password-free entry.",
    worldLink: "Open the World section →",
    achTitle: "Achievements",
    achBody: "Ratings, streaks and rewards will appear along with game progress.",
    tagDone: "Done",
    tagSoon: "Soon",
  },
  schedule: {
    title: "Schedule",
    sub: "{name} · classes and attendance from the CRM (updated automatically)",
    weekBack: "← Previous week",
    weekCurrent: "Current week",
    weekFwd: "Next week →",
    loadError: "Could not load the schedule. Try refreshing the page.",
    empty: "No classes this week. Switch the child's profile or check neighbouring weeks.",
    today: "today",
    visited: "✓ attended",
    missed: "absent",
    unknown: "no mark",
    wd: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    months: [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    ],
  },
  words: {
    title: "Word trainer",
    sub: "{name} · word lists by level and textbook",
    learned: "words learned",
    dueToday: "to review today",
    accuracy: "answer accuracy",
    loadError: "Could not load word lists. Try refreshing the page.",
    empty: "Word lists will appear here — public level sets and sets assigned by your teacher.",
    kindLevel: "Level",
    kindBook: "Textbook",
    kindTopic: "Topic",
    setProgress: "{learned}/{total} · {due} to review",
    train: "Train →",
  },
  train: {
    loading: "Preparing your training…",
    back: "← Word lists",
    backToSets: "← Back to word lists",
    speakTitle: "Play audio",
    promptInput: "Type the word for this translation:",
    check: "Check",
    correct: "Correct!",
    wrong: "Correct answer:",
    listen: "🔊 Listen to the word",
    finish: "Finish",
    next: "Next →",
    startError: "Could not start the training. Please try again.",
    doneTitle: "Done!",
    doneSub: "{correct} of {all} correct{pct}. Words you got wrong will return to today's training.",
    again: "Once more",
    toSets: "← To word lists",
  },
  world: {
    title: "Foxinburg World",
    sub: "{name} · castle, Spotlight towers and leagues",
    level: "level",
    xp: "XP",
    coins: "coins",
    streak: "days in a row",
    towers: "World towers",
    towerSpotlight: "Spotlight tower",
    towerLevel: "level {level}",
    league: "League of the week",
    leagueBody: "Rank {rank} · {xp} XP this week",
    notStartedTitle: "The journey hasn't started yet",
    notStartedSub: "{name} hasn't been to the Foxinburg World yet. Enter — the castle, the Spotlight tower and the first league are waiting!",
    enterSubLinked: "Password-free entry — the account opens the World for {name}.",
    enter: "Enter the Foxinburg World",
    entering: "Opening the World…",
    loadError: "Could not load World progress. Try refreshing the page.",
    enterError: "Could not enter the World. Please try again.",
  },
};

export const DICTS: Record<Lang, Dict> = { ru: RU, en: EN };

// Подстановка {placeholders} — единственная «логика» в словаре.
export function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
}

function readStoredLang(): Lang {
  if (typeof window === "undefined") return DEFAULT_LANG;
  return window.localStorage.getItem(LANG_KEY) === "en" ? "en" : DEFAULT_LANG;
}

type I18n = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Dict;
};

const I18nContext = createContext<I18n>({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: RU,
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  // После монтирования подхватываем сохранённый язык (гидратация безопасна:
  // серверный и первый клиентский рендер совпадают — RU).
  useEffect(() => {
    setLangState(readStoredLang());
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = lang;
    }
  }, [lang]);

  const setLang = (l: Lang) => {
    setLangState(l);
    if (typeof window !== "undefined") window.localStorage.setItem(LANG_KEY, l);
  };

  return (
    <I18nContext.Provider value={{ lang, setLang, t: DICTS[lang] }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18n {
  return useContext(I18nContext);
}
