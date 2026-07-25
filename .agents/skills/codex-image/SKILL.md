---
name: codex-image
description: Generate a cover/banner/illustration image via gpt-image-2 through a ChatGPT/Codex subscription (no separate OpenAI API key or per-image charge). Use when the owner asks for a site image, /novosti article cover, or social banner — but only after codex login is confirmed (see Blocked below).
---

# codex-image — covers via Codex subscription

Adapted from EdgeLab's `skill-codex-image`. **Blocked on owner action, do not
attempt to work around it:**

1. Requires an active ChatGPT or Codex subscription (Plus ~$20/mo or higher)
   — a new recurring payment decision, squarely in this project's red zone
   (`CLAUDE.md`: "любые платные подписки/API"). Confirm with the owner before
   assuming this exists.
2. Requires `codex login` (interactive OAuth, creates `~/.codex/auth.json`)
   — this has to be run by the owner on their own machine/session, an agent
   cannot complete browser OAuth on their behalf.
3. The actual skill script (`run.sh` + venv) lives in
   `github.com/qwwiwi/agentos-skills-public/tree/main/skills/codex-image` and
   isn't pulled into this repo yet — install via `npx skills add
   github.com/qwwiwi/agentos-skills-public --skill codex-image` once 1–2 are
   confirmed.

## What it does once unblocked
Calls gpt-image-2 through the OpenAI **Responses API** (`image_generation`
tool, not the paid Images API) using the subscription's own OAuth token —
so images come out of the subscription quota, not a per-image charge.

## Pipeline (for reference)
```
run.sh "english prompt describing the image, with exact caption text" [quality] [aspect] [ref1..ref5]
```
- `quality`: low (~45s) / medium (~1-2min) / high (~2-3min)
- `aspect`: landscape (1536x1024) / square (1024x1024) / portrait (1024x1536)
- up to 5 reference images (style/face/logo) transfer style and likeness
- write the prompt in English; Cyrillic caption text on the image renders
  cleanly, but avoid the → arrow glyph — spell out "to"/"до"
- no `seed` parameter — for strict reproducibility, a paid image API is
  needed instead

## When not to use
- Deterministic graphics with exact typography/brand colors (avatars, strict
  banners, diagrams) — build those as SVG, don't generate them.

## Where this could plug in
`.agents/skills/seo-content-engine` step 7 (cover for a /novosti article) —
only once subscription + login are confirmed and the skill is actually
installed.
