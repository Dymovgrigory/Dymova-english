---
name: datawrapper
description: Publish a chart or table (from CSV/JSON/inline data) to Datawrapper and export PNG — for embedding audit/funnel numbers into a report, Telegram message, or DEVLOG entry instead of a raw markdown table. Use on "сделай график", "визуализируй данные", "chart из этой таблицы".
---

# Datawrapper Charts

Adapted from EdgeLab's `skill-datawrapper`. **Blocked on owner action**: the
source repo bundles a ready `scripts/datawrapper_chart.py` CLI; it wasn't
pulled in here because installing it requires `npx skills add
github.com/qwwiwi/agentos-skills-public --skill datawrapper` with the
owner's explicit go-ahead (see project `CLAUDE.md` red zone — external code
install). Even with the script, this skill needs a `DATAWRAPPER_API_KEY`
(free Datawrapper account, no payment, but still an account only the owner
can create: https://app.datawrapper.de/account/api-tokens, scopes
`chart:write chart:read theme:read visualization:read`).

Until both are in place, call the Datawrapper REST API directly (`POST
/v3/charts`, `PUT /v3/charts/{id}/data`, `POST /v3/charts/{id}/publish`,
`GET /v3/charts/{id}/export/png`) per https://developer.datawrapper.de/ — the
chart-type table and defaults below still apply.

## When to use
- Owner wants a chart/table from data (e.g. funnel numbers from
  `sales-funnel-agent`, or an audit metric from `AUDIT_OBSHIY.md`).
- Result needs to be shareable via URL or embeddable as PNG in a message.

## When not to
- A local matplotlib/inline image with no hosting need is enough.
- Need PDF/SVG export — that's a paid Datawrapper plan.

## Chart types

| Visual | Type ID |
|--------|---------|
| Bar (horizontal) | `d3-bars` |
| Stacked bar | `d3-bars-stacked` |
| Column (vertical) | `column-chart` |
| Line | `d3-lines` |
| Area | `d3-area` |
| Pie | `d3-pies` |
| Scatter | `d3-scatter-plot` |
| Table | `tables` |

## Input formats
CSV file/text, JSON (array of objects or `{columns, rows}`), or an inline
pipe table auto-detected by splitting on `|`. Free plan: unlimited
create/publish/PNG export, with a "Created with Datawrapper" watermark.
