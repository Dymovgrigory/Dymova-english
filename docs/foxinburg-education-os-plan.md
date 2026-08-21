# Foxinburg Education OS — рабочий план (от владельца, 2026-08-07)

Стратегический план развития LMS/админки Фоксинбурга в полноценную
«Foxinburg Education OS». Источник — сообщение владельца; документ —
точка входа для всех последующих сессий по этой теме. Детальный
рабочий промт владелец пришлёт отдельно.

## Принцип

Не собирать «Frankenstein-проект» из десятков GitHub-репозиториев.
Использовать лучшие библиотеки и их архитектурные подходы.

## Библиотечный стек

| Библиотека | Роль |
|---|---|
| **shadcn/ui** | Основа Design System. Полный контроль компонентов, semantic CSS variables, темизация. |
| **Craft.js** | React-фреймворк для собственного drag-and-drop page editor (не готовая админка, а конструктор редактора). |
| **dnd-kit** | Drag & drop: конструктор курсов, модули, уроки, блоки, CMS, sortable lists, nested layouts. Keyboard/touch/pointer + accessibility. |
| **Tiptap** | Редактор контента LMS/CMS. Headless, extensible, собственный UI вместо «Word 2003 toolbar». (Уже внедрён в LMS PR #118/#119.) |
| **TanStack Table** | Таблицы Students / Teachers / Courses / Payments / Analytics: sorting, filtering, grouping, selection, virtualization, server-side. |

## MCP-стек

```
Kimi
├── Context7          — актуальная документация библиотек
├── GitHub MCP        — repositories / issues / releases / code research
├── Filesystem MCP    — работа с проектом
├── Playwright MCP    — E2E / browser QA / interaction testing
└── Chrome DevTools MCP — performance / console / network / debugging
```

**Правило:** НЕ ставить `@latest` в production-конфигурацию MCP.
Перед обновлением MCP — проверять release notes и compatibility
(в 2026 были регрессии Playwright MCP на macOS). Версии зафиксированы
в `~/.kimi-code/mcp.json` (2026-08-07): playwright 0.0.79,
chrome-devtools 1.6.0, context7 4.0.0, github 2025.4.8,
filesystem 2026.7.10. Обновление — только осознанно, после проверки.

## Skills (`~/.kimi-code/skills/`)

Foxinburg-specific слой поверх существующих (admin-panel-builder,
animations-gsap, code-reviewer, database-architect,
edtech-platform-builder, frontend-architecture — не удалять):

- foxinburg-design-system
- foxinburg-admin-ux
- foxinburg-lms-builder
- foxinburg-visual-cms
- foxinburg-editor
- foxinburg-component-architecture
- foxinburg-responsive
- foxinburg-accessibility
- foxinburg-performance
- foxinburg-security
- foxinburg-playwright
- foxinburg-visual-qa
- foxinburg-database
- foxinburg-release

## Целевая архитектура

```
FOXINBURG ADMIN
│
├── Website
│   ├── Pages
│   │   └── Visual Editor
│   │       ├── Layers
│   │       ├── Block Library
│   │       ├── Canvas
│   │       └── Inspector
│   ├── Navigation
│   ├── Global Styles
│   ├── Media
│   └── SEO
│
├── LMS
│   ├── Courses
│   │   └── Course Builder
│   │       ├── Modules
│   │       ├── Lessons
│   │       └── Quizzes
│   ├── Students
│   ├── Teachers
│   ├── Homework
│   ├── Attendance
│   └── Certificates
│
├── BUSINESS
│   ├── Payments
│   ├── Leads
│   ├── Communications
│   └── Analytics
│
└── SYSTEM
    ├── Users
    ├── Roles
    ├── Permissions
    ├── Integrations
    ├── Audit Log
    └── Settings
```

## Ключевая архитектурная идея: единый Block Engine

Website Editor и LMS Editor используют **одну block architecture**:

```
Block Engine
├── TextBlock
├── ImageBlock
├── VideoBlock
├── ButtonBlock
├── CardBlock
├── CourseBlock
├── TeacherBlock
├── QuizBlock
├── HomeworkBlock
├── CTA
├── Gallery
└── CustomBlock
```

CMS — не набор страниц с формами. Целевой UX:
администратор выбирает блок → перетаскивает → меняет свойства →
сразу видит результат → сохраняет draft → сравнивает версии → публикует.

Результат — не «админка языковой школы», а Foxinburg Education OS.
