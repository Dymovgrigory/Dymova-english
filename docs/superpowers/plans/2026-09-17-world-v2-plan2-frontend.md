# World v2 — План 2: фронтенд (урок, путь, онбординг) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Новый интерфейс тренажёра поверх `/api/v2`: онбординг «Мой класс», путь модулей, полноэкранный урок в стиле Duolingo, тренировка, словарь, профиль; замок остаётся на `/world`.

**Architecture:** Клиентские страницы Next 16 (`"use client"`), тонкий клиент `src/lib/v2/client.ts`, чистая логика урока и раскладки пути в тестируемых модулях (`lessonState.ts`, `pathLayout.ts`), компоненты дизайн-системы в `src/design/`, экраны в `src/features/`.

**Tech Stack:** Next 16.3, React 19.2, Tailwind 4, motion 13, vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-17-foxinburg-world-v2-spotlight-engine-design.md` (раздел 7)

## Global Constraints

- Цвета бренда: фиолетовый `#3a2953`, жёлтый `#f5ed75`, бирюзовый `#7fd8c9`; ошибка `#ff6b5e`.
- Шрифты: Nunito (текст), Montserrat ExtraBold (заголовки модулей) — уже подключены в `layout.tsx`.
- Зоны нажатия ≥ 48 px, фокус-кольца, `aria-live` для результата, `prefers-reduced-motion`.
- Новые экраны не наследуют тёмный фон замка: обёртка `.study` задаёт свой фон.
- `useSearchParams` не используем (требует Suspense при сборке) — параметры через `useParams`.
- Картинки контента: `/content/<image>`; нет файла → текстовая плитка вместо картинки.

## Design plan

**Идея:** «тетрадь в клетку, королевские печати». Учёба в Фоксинбурге выглядит как школьная тетрадь: светлая бумага с тонкой лавандовой клеткой (связь со школой и учебником), а узлы пути — объёмные сургучные печати замка. Смелость тратим в одном месте — на путь; урок тихий и собранный.

| Токен | Hex | Роль |
|---|---|---|
| paper | `#FBFAFF` | фон учёбы (холодный белый, не кремовый) |
| grid | `#E9E4F5` | клетка тетради |
| ink | `#2A1F3D` | основной текст |
| royal | `#3A2953` | заголовки, печати пройденных узлов, нижнее меню |
| crown | `#F5ED75` / кромка `#D8B72C` | главная кнопка, текущий узел |
| mint | `#7FD8C9` / текст `#1E7F70` | верно |
| coral | `#FF6B5E` / текст `#B8352B` | ошибка |

Типографика: заголовок урока 26/32 Nunito ExtraBold; варианты ответа 20/26 Bold; инструкция 22/28 ExtraBold; название модуля на пути — Montserrat ExtraBold 22, английское название как в учебнике крупно, русское — мелко под ним.

Раскладка урока:
```
[×] [██████░░░░░░]            ← прогресс
Выбери перевод                 ← инструкция (слева)
         cat  🔊               ← задание
[ кошка ] [ собака ] [ мама ]  ← варианты (сетка/столбец)
────────────────────────────
[        Проверить          ]  ← липкая нижняя панель → лист результата
```
Путь: узлы-печати змейкой по клетке, плашка модуля «липнет» сверху; текущая печать жёлтая с мягким пульсом и подписью «Начать».

## File Structure

```
world/src/
  lib/v2/types.ts          # типы ответов /api/v2
  lib/v2/client.ts         # fetch-клиент + ensurePlayer
  lib/v2/lessonState.ts    # редьюсер урока (очередь, выбор, проверка)   + .test.ts
  lib/v2/pathLayout.ts     # смещения змейки, подписи узлов            + .test.ts
  lib/v2/speech.ts         # распознавание речи (Web Speech)
  lib/v2/media.ts          # url картинки контента
  design/{Button,ProgressBar,Choice,Tile,FeedbackSheet,Seal,StatPill,Sound,Foxy,Shell}.tsx
  features/lesson/{LessonScreen,ChallengeView,TeachCard,ChoiceChallenge,TilesChallenge,PairsChallenge,TypeChallenge,SpeakChallenge,FinishScreen}.tsx
  features/path/PathScreen.tsx
  features/onboarding/Onboarding.tsx
  features/words/WordsScreen.tsx, features/practice/PracticeScreen.tsx, features/profile/ProfileScreen.tsx
  app/{page,onboarding/page,learn/page,lesson/[nodeId]/page,practice/page,words/page,profile/page}.tsx
  app/globals.css          # + токены .study
next.config.ts             # + прокси /api/v2
```

### Task 1: Типы, клиент, логика урока и пути (TDD)
- [ ] `lessonState.test.ts`: старт → первый индекс; `select` активирует «Проверить»; `graded` ответ с `requeued` ставит индекс в конец; teach-карточка проходит без проверки; `done` когда очередь пуста; прогресс = решённые оцениваемые / всего.
- [ ] `pathLayout.test.ts`: смещение по синусоиде в пределах ±amplitude, текущий узел находится.
- [ ] реализация, `npm test` зелёный, commit.

### Task 2: Дизайн-система + токены
- [ ] компоненты `src/design/*`, токены `.study` в `globals.css`, commit.

### Task 3: Экран урока и финиш
- [ ] все 18 типов заданий рендерятся; клавиатура 1–4/Enter; звук верно/неверно; лист результата с `aria-live`; финиш с XP, точностью, временем, серией и целью; commit.

### Task 4: Путь, онбординг, меню, главная
- [ ] `/` решает: нет игрока → `/onboarding`, нет профиля → `/onboarding`, иначе `/learn`; онбординг: имя → класс → модуль → цель → старт первого узла; путь с переключателем книг и сундуками; нижнее меню / левая колонка; commit.

### Task 5: Тренировка, словарь, профиль, вкладка замка
- [ ] экраны + пустые состояния; commit.

### Task 6: Удаление старого фронта, e2e и проверка
- [ ] удалить `app/learn/[lessonId]`, `learn/album`, `learn/sprint`, неиспользуемые `ui/*` урока v1; Playwright: онбординг → урок до финиша → путь; 390 и 1440 px; `tsc`, `eslint`, `vitest`, `next build`; commit.
