---
name: excalidraw
description: Generate an Excalidraw diagram (.excalidraw JSON v2) — pipeline, mindmap, flowchart, sequence, or freeform — for architecture sketches, funnel/pipeline visuals, or explaining a flow to the owner. Use on "нарисуй схему", "flowchart", "mindmap", "sequence diagram", "визуализируй архитектуру".
---

# Excalidraw Diagrams

Adapted from EdgeLab's `skill-excalidraw`. The source repo bundles a
`scripts/excalidraw_gen.py` generator; that script wasn't pulled in here
(installing it needs `npx skills add github.com/qwwiwi/agentos-skills-public
--skill excalidraw` with the owner's explicit go-ahead — see project
`CLAUDE.md` red zone). The JSON format below is fully specified, so a diagram
can be written directly as a `.excalidraw` file without the helper script;
only fetch the script from the source repo if hand-writing JSON becomes a
recurring bottleneck.

## Diagram types

| Type | Use for |
|------|---------|
| `pipeline` | Vertical flow with stages (e.g. the 8-gate SEO pipeline) |
| `mindmap` | Radial map from a central topic |
| `flowchart` | Arbitrary graph: nodes + edges (e.g. site/bot architecture) |
| `sequence` | Actor/message sequence (e.g. lead → bot → CRM handoff) |
| `freeform` | Raw Excalidraw elements, full control |

## Visual standards

- `fontFamily: 1` (hand-drawn). Body/labels 18px (min 16), stage headers 20px,
  titles 28px, secondary annotations 14px — never below 14.
- Min shape 120x60 for labeled rectangles; 20–30px gaps between elements.
- Camera must stay 4:3: S 400x300, M 600x450, L 800x600 (default), XL
  1200x900, XXL 1600x1200.
- Color-by-role mapping: input `#ffc9c9`/`#ef4444`, research `#a5d8ff`/`#4a9eed`,
  analysis `#d0bfff`/`#8b5cf6`, review `#ffd8a8`/`#f59e0b`, final `#b2f2bb`/`#22c55e`,
  storage `#c3fae8`/`#06b6d4`, warning `#fff3bf`/`#f59e0b`, metrics `#eebefa`/`#ec4899`.
- Text contrast: min `#757575` on white; dark variants (`#15803d`, not
  `#22c55e`) on colored fills; white text only on dark backgrounds.
- Emoji don't render in the Excalidraw font — use text instead.

## JSON shape by type

### Pipeline
```json
{
  "title": "8-Gate SEO Pipeline",
  "type": "pipeline",
  "dark": false,
  "stages": [
    {"label": "1. БРИФ", "color": "input", "blocks": [{"text": "Тема\nЗапросы"}]},
    {"label": "2. ИСТОЧНИКИ", "subtitle": "параллельно", "color": "research",
     "blocks": [{"text": "Perplexity"}, {"text": "Опыт школы", "color": "analysis"}]}
  ]
}
```

### Mindmap
```json
{"title": "Тема", "type": "mindmap", "nodes": [
  {"text": "Ветка 1", "color": "research"},
  {"text": "Ветка 2", "color": "analysis"}
]}
```

### Flowchart
```json
{"title": "Architecture", "type": "flowchart",
 "nodes": [
   {"id": "site", "x": 0, "y": 0, "text": "Tilda site", "color": "analysis"},
   {"id": "bot", "x": 300, "y": 0, "text": "MAX bot", "color": "research"},
   {"id": "crm", "x": 300, "y": 200, "text": "BigBen CRM", "color": "storage"}
 ],
 "edges": [{"from": "site", "to": "bot", "label": "chat"}, {"from": "bot", "to": "crm", "label": "lead"}]
}
```

### Sequence
```json
{"title": "Lead handoff", "type": "sequence",
 "actors": [{"id": "user", "name": "User"}, {"id": "bot", "name": "Bot"}, {"id": "crm", "name": "BigBen"}],
 "messages": [
   {"from": "user", "to": "bot", "label": "вопрос"},
   {"from": "bot", "to": "crm", "label": "создать лид"},
   {"from": "crm", "to": "bot", "label": "lead_id", "response": true}
 ]}
```

### Freeform (raw elements — full control)
```json
{"type": "freeform", "elements": [
  {"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0},
  {"type": "rectangle", "id": "b1", "x": 100, "y": 100, "width": 200, "height": 80,
   "roundness": {"type": 3}, "backgroundColor": "#a5d8ff", "fillStyle": "solid",
   "label": {"text": "Start", "fontSize": 20}}
]}
```

Drawing order = z-order: background → shapes → arrows. Use `fixedPoint` on
arrow bindings for exact side attachment. Labeled shapes save tokens over a
separate text element. Save the result as `<name>.excalidraw`, openable at
excalidraw.com.
