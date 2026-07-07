---
name: session-journal
description: >-
  Maintain the detailed handoff journal (DEVLOG.md) for the Dymova-english /
  Foxinburg project. Use at the START of every session (to load context) and
  before EVERY pull request (to append a detailed journal entry), so any future
  agent can continue the work seamlessly. The owner (Skyler / Dymovgrigory)
  explicitly requires a detailed journal entry for every PR, automatically.
---

# Session Journal (Журнал сессий) — Foxinburg / Dymova-english

The owner wants every agent to **continue seamlessly** after the previous one
and to **record a detailed journal entry for every PR, automatically**. The
journal lives at `DEVLOG.md` in the repository root. It is the single source of
truth for project history, decisions, credentials map, deploy state, and "where
we stopped".

## 1. At the start of EVERY session

1. Read `DEVLOG.md` top-to-bottom — especially the latest "Сессия N" entry and
   the **"Текущий статус / Где остановились"** section near the end.
2. Read `PROMPT_FOXINBURG.md` (site/task spec) if the task touches the Tilda
   site, and `bot/README.md` + `bot/DEPLOY.md` if the task touches the MAX bot.
3. Check open/merged PRs with the `git_view_pr` tool to confirm what already
   shipped.
4. Only then start the actual task.

## 2. Before EVERY pull request (mandatory)

Append a new journal entry to `DEVLOG.md` **in the same PR** as the code change
(so journal and code never drift apart). Never open a PR with code changes
without a matching journal entry. Write in Russian, matching the existing file.

Use this template (fill every field; omit a line only if truly N/A):

```
### Сессия N (агент — Devin, <короткое описание>) — PR #<NN>

**Дата:** <YYYY-MM-DD>
**PR:** #<NN> — <заголовок> (<ветка> → main)
**Запрос владельца:** <что попросил Skyler, дословно/кратко>

**Что сделано:**
- <изменение 1 — какой файл/функция и зачем>
- <изменение 2 ...>

**Как проверено:**
- тесты: `cd bot && pytest -q` → <N passed>
- живые сценарии / ручная проверка: <если была>

**Решения и нюансы:** <почему так, что не очевидно из диффа>
**Деплой:** <переразвёрнут ли прод; если нет — почему (напр. нет SSH)>
**Осталось / следующий шаг:** <что не доделано, что делать дальше>
```

After writing the entry, `git add DEVLOG.md` together with the code, commit, and
open the PR (follow the normal PR flow: `fetch_pr_template` → `git_create_pr`).

## 3. Keep the handoff section current

Near the end of `DEVLOG.md` there is a **"Текущий статус / Где остановились"**
block. Update it every PR so the next agent sees the live state at a glance:
- last merged PR number + one line on what it did;
- whether prod was redeployed from `main`;
- the immediate next step / open decision waiting on the owner.

## 4. Mirror the handoff into a knowledge note

When you finish a session, also keep the Devin **knowledge note** "Foxinburg /
Dymova-english — handoff" up to date (via `suggest_knowledge`, action `update`)
so it is auto-injected into future sessions even before DEVLOG.md is read. Keep
it short: last PR, prod state, key IDs (see `DEVLOG.md` → "Ключевые значения"),
and the next step. Never put secrets/tokens in the note or in DEVLOG.md.

## 5. Quick reference

- Bot tests: `cd bot && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pytest -q`
- CI: `.github/workflows/bot-ci.yml` runs `pytest -q` on any change under `bot/**`.
- Bot lives in `bot/` (FastAPI + MAX + BigBen CRM + LLM). Site work is in Tilda
  (project 2053071) and prototypes in `prototype/` — see DEVLOG sessions 1–8.
- Key IDs / endpoints / deploy notes: `DEVLOG.md` → "Ключевые значения" and the
  bot "Что осталось сделать" subsection. Secrets are env-only, never committed.
