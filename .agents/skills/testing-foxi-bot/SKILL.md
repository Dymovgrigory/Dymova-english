---
name: testing-foxi-bot
description: Test the Foxi chat bot (bot/ FastAPI app) end-to-end — KB-grounded answers, anti-hallucination admin handoff, lead signup flow, insights journal and /admin/insights. Use when verifying bot answer quality or chat widget behavior.
---

# Testing the Foxi Bot End-to-End

## Overview

The bot lives in `bot/` (FastAPI). Channels: MAX webhook, Telegram long-polling, and a web widget (`/widget/foxi.js`) that talks to `POST /api/chat`. For end-to-end UI testing, run the bot locally and use the widget on a test page.

## Devin Secrets Needed

- `LLM_API_KEY` — OpenRouter key. **Strip whitespace!** The stored value may have a trailing space that makes every LLM call fail with `httpx.LocalProtocolError: Illegal header value` — then the bot answers everything with "передал администратору". Always launch with `LLM_API_KEY=$(echo -n "$LLM_API_KEY" | tr -d '[:space:]')`.
- `MAX_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN` — only needed for channel-specific tests, not for /api/chat.

## Setup

```bash
cd bot && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
LLM_API_KEY=$(echo -n "$LLM_API_KEY" | tr -d '[:space:]') \
LLM_MODEL=openai/gpt-4o-mini \
ADMIN_MAX_IDS=999000111 ADMIN_TOKEN=testtoken \
INSIGHTS_FILE=./data/insights.jsonl \
nohup python run_local_test.py > /tmp/bot.log 2>&1 &
```

- `run_local_test.py` serves the bot at `http://localhost:8000`, mounts the widget at `/widget/foxi.js`, and a test page with the embedded widget at `/test-page`. If it doesn't exist, create a small FastAPI wrapper mounting `app.main:app` plus a static test page.
- The default free model (`meta-llama/llama-3.3-70b-instruct:free`) is frequently rate-limited (429) upstream — if all replies become admin referrals, check `/tmp/bot.log` for 429s and switch `LLM_MODEL` to a paid model like `openai/gpt-4o-mini`.
- `ADMIN_MAX_IDS` pointing to a fake user makes admin notification sends 404 in the log — harmless for testing.

## Common Pitfalls

- **Cyrillic can't be typed via computer-use keyboard** (xdotool drops non-ASCII; only punctuation like `!` gets through, so the bot receives "!"). Workaround: put the text on the clipboard and paste:
  ```bash
  printf 'Текст вопроса' | DISPLAY=:0 xclip -selection clipboard
  ```
  then click the widget textarea and press Ctrl+V.
- Sanity-check the LLM path with `curl -s localhost:8000/api/chat -H 'Content-Type: application/json' -d '{"text":"Что умеешь?"}'` BEFORE starting a recording — if it returns the admin-referral phrase, the LLM is down (key/rate-limit), not the bot logic.
- Delete `data/insights.jsonl` before testing so journal assertions are clean.
- Once a conversation is handed off to admin, subsequent unknown questions in the same session get a short "уже передал администратору" reply and are NOT re-logged to insights.

## Test Scenarios

1. **Cold client**: "Расскажите про вашу школу" → confident facts only from `app/knowledge/data.yaml` (Долгопрудный, 2–18 лет + взрослые, мини-группы ≤7, англ/нем/кит). "Сколько стоит…" → only KB prices, no invented figures.
2. **Signup flow**: "Хочу записаться на пробное занятие" → bot collects parent name, child name, age, phone, branch, shows summary, confirms after «да».
3. **Anti-hallucination**: ask about things not in the KB (director's name, made-up discounts, teacher salaries) → bot must NOT invent anything; expect soft admin handoff with branch phones (8 993 923-23-09 / 8 916 732-31-69).
4. **Insights**: check `data/insights.jsonl` entries (hashed uid, reason `no_kb_match`/`weak_kb_match`/`llm_uncertain`); `GET /admin/insights?days=1&top=20` with `X-Admin-Token` → 200 summary; without token → 401.

## Reporting

- Record widget interactions with annotations; verify insights/endpoint via shell (no recording needed for shell-only parts).
- Post ONE PR comment with results and embedded screenshots; attach test-report.md + recording to the final user message.
