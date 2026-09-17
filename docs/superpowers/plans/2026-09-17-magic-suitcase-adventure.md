# Magic Suitcase Adventure — Implementation Plan

> **For Claude:** execute task-by-task. Autopilot approved by owner 2026-09-17.

**Goal:** Teacher-paced 22-scene HTML/JS quest in `presentations/magic-suitcase/`.

**Spec:** `docs/superpowers/specs/2026-09-17-magic-suitcase-adventure-design.md`

## Files

| File | Role |
|------|------|
| `presentations/magic-suitcase/index.html` | Shell 16:9 stage + nav chrome |
| `presentations/magic-suitcase/css/adventure.css` | Layout, ambient, click anims, transitions |
| `presentations/magic-suitcase/js/assets.js` | Word/image URL manifest |
| `presentations/magic-suitcase/js/scenes.js` | All 22 scene configs |
| `presentations/magic-suitcase/js/engine.js` | Scene load, history, MAP, anim helpers |
| `presentations/magic-suitcase/js/app.js` | Boot |

## Tasks

1. Scaffold HTML + CSS stage (16:9, Back, MAP, next).
2. Engine: goTo, back, map overlay, flyToSuitcase, shake, glow, bounce, transitions.
3. Scenes 1–7 (cover → furniture).
4. Scenes 8–13 (family → weather/clothes).
5. Scenes 14–22 (animals → goodbye + memory + worksheet).
6. Smoke-test in browser / static server.

## Test

```bash
cd presentations/magic-suitcase && python3 -m http.server 8765
# open http://localhost:8765 — click through School pack, wrong click shake, MAP jump, Back
```
