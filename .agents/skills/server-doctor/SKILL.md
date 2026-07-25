---
name: server-doctor
description: Systematically audit and diagnose the Foxinburg bot's production host — map what's running, find hung processes/memory leaks/log errors, before guessing at a fix. Use when the bot (MAX/Telegram) is down, slow, or erroring.
---

# Server Doctor — infra audit

Adapted and trimmed from EdgeLab's `skill-server-doctor` (the original also
covers OpenClaw-gateway and Telegram-specific incident playbooks that don't
apply to this project's stack — FastAPI/uvicorn bot, not OpenClaw — so those
sections were dropped rather than carried over verbatim).

**Known prod target** (per `DEVLOG.md` → "Текущий статус", latest commit
2026-07-07 — newer and more reliable than `wiki/07-bot-i-crm.md`, which
still says hosting isn't set up and should be treated as stale on this
point): VM `yc-user@89.169.132.104` (Yandex Cloud), deployed from `main` via
`docker compose -f docker-compose.prod.yml up -d --build` in
`~/Dymova-english/bot`. SSH key: secret `VPS_SSH_PRIVATE_KEY_OWNER`
(`~/.ssh/foxinburg_vps` locally). Nginx `foxinburg-frontend` proxies
`bot.dymova-english.ru` → container `bot-bot-1:8000`. Telegram runs via
long-polling + SOCKS5 proxy (РКН blocks direct in/outbound to
api.telegram.org from RU IPs) — `TELEGRAM_POLLING=true`,
`TELEGRAM_PROXY_URL` in prod `.env`. MAX webhook:
`https://bot.dymova-english.ru/webhook`.

Always re-check `DEVLOG.md` → "Текущий статус" before relying on the above —
it may have moved on since 2026-07-07.

## When to use
Bot reported down/slow/erroring on MAX or Telegram, before guessing at a fix.

## Workflow

### 1. Access & inventory preflight
Before diagnosing, get the minimum map:
- host/machine, access method (ssh/tailscale/local shell/docker exec)
- which Unix user or container owns the bot process
- runtime style: systemd / launchd / Docker-Compose / direct process / tmux

Don't demand secrets be pasted into chat — the requirement is an access
path, not credentials in the open.

### 2. Host context (low-risk, read-only)
```bash
hostname && whoami && uname -a && uptime
df -h && free -h            # Linux
ps -eo user,pid,ppid,cmd --sort=user
ss -tulpn                   # Linux
```
macOS equivalents: `sw_vers`, `ps aux`, `launchctl list`.

### 3. Discover runtimes
```bash
systemctl --failed
systemctl list-units --type=service --all
docker ps -a && docker compose ls
```

### 4. Locate project state
```bash
find ~ -maxdepth 3 -type d | grep -Ei 'dymova|foxinburg|bot'
```
Known project location: `bot/app/` (FastAPI app), `bot/app/knowledge/`
(knowledge base). Config vars: `MAX_BOT_TOKEN`, `LLM_API_KEY`, `BIGBEN_*`
(per `wiki/07-bot-i-crm.md` — never print their values).

### 5. Classify before acting
Separate spec correctness (right host/runtime/target, evidence-backed
wording) from ops quality (healthy / degraded / partial failure / unstable /
down). Don't jump from partial visibility straight to "outage" language —
incomplete visibility isn't outage proof, and restart alone isn't recovery.

### 6. Document
For the discovered service: host, owning user, runtime style, working
directory, log path, restart command, dependencies, known failure modes,
remaining unknowns. Never print secrets/tokens/passwords into the report or
commit them — redact IPs, hostnames, tokens.

## Not carried over from the original
OpenClaw-specific incident playbooks, private helper scripts
(`normalize-openclaw-models.py` etc.) and the Caddy/Next.js safe-deploy
contract from the source material are specific to another team's stack and
don't apply here. If a `bot/` deploy pipeline is built later, write its own
safe-deploy notes based on what FastAPI/uvicorn actually needs, rather than
importing those verbatim.
