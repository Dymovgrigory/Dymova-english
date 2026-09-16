# API.md — World HTTP contracts

Prefix: `/api/world`  
Auth: header `X-World-Player` — opaque session token `wses.*` from `POST /players`, or legacy HMAC (`auth.py`). TTS also requires the header. Public create is child-only.

## Players

| Method | Path | Notes |
|---|---|---|
| POST | `/players` | get-or-create; returns `token` |
| GET | `/player` | snapshot |

## Learn

| Method | Path | Notes |
|---|---|---|
| GET | `/learn/home` | player, hearts, quests, stickers, `current_lesson_id`, **`next_best_action`** |
| GET | `/learn/path` | units + locks + stars |
| POST | `/learn/lessons/start` | body `{lesson_id}` |
| POST | `/learn/sessions/{id}/answer` | server grade |
| POST | `/learn/sessions/{id}/finish` | award + SRS |
| POST | `/learn/practice/start` | yard |
| GET | `/learn/review` | due words |
| GET | `/learn/words/{unit}` | stats |
| GET | `/learn/shop` | SKUs |
| POST | `/learn/shop/buy` | stable idempotency |
| POST | `/learn/hearts/restore` | paid alias of refill SKU |
| GET/POST | `/learn/sprint` | capped daily reward |
| GET/POST | `/learn/quests` + `/claim` | dailies |
| GET | `/learn/stickers` | album |
| GET | `/learn/league` | weekly |

## World meta

quests start/step/complete · inventory · unlocks · activities (legacy challenge path).

## Errors

404 `NotFound` · 409 `Conflict` (hearts, locks) · 401 missing/bad player · 422 bad role.

## Typing

Pydantic on write bodies; response currently dict. Target: shared JSON schema version field `schema_version` on home.
