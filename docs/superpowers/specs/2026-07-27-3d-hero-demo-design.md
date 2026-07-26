# 3D Hero Demo — Design Spec

Date: 2026-07-27
Status: Approved

## Purpose

A standalone, throwaway visual prototype to evaluate whether a Three.js-driven 3D hero
(in the style circulating in "AI-built 3D sites" demos, e.g. getlayers.ai) fits the
Dymova English / Foxinburg brand. Not intended for production integration — a single
file to open in a browser and judge on style fit alone.

## Brand context (why this isn't a generic template)

Current site (`prototype/main_combined_v7.html`) uses a playful, mascot-driven identity:
fox mascot (`brand-assets/fox-head-*.png`), hand-drawn decorative blobs/swirls, and a
bold palette — purple `#662d92`/`#392852`, yellow `#fcf951`, coral `#ee7349`, green
`#2bb673`. This is closer to "Playful/Organic" than the "Dark/Luxe/Technical" mood most
AI-template 3D scenes default to, so the scene content and palette are constrained to
match, not copied wholesale from reference sites.

## Scope decisions (from user)

- **3D subject**: abstract floating forms in brand colors — no fox mascot, no lettering.
- **Interactivity**: scroll-reactive (forms shift/rotate as the page scrolls), not
  mouse-parallax, not idle-only.
- **Mobile**: same scroll-reactive 3D scene everywhere, simplified geometry — no static
  image fallback.
- **Deliverable**: single self-contained `.html` file, Three.js via CDN import map, no
  build step — directly comparable to how the existing Tilda static site is served.

## Architecture

Single file: `docs/prototypes/hero-3d-demo.html`.

- `<head>`: `<script type="importmap">` pointing `three` at a CDN (unpkg) build.
- Full-bleed `<canvas>` behind placeholder hero text + CTA button (using the brand
  palette, not real copy).
- One `<script type="module">` containing all Three.js setup, scene, render loop.

## Scene composition

5 meshes: sphere, torus, icosahedron ×2 (different scales), rounded box. Each:

- `MeshPhysicalMaterial`: `roughness ≈ 0.2`, `transmission ≈ 0.6`, color = one of the
  4 brand hex values.
- Vertex shader adds simplex-noise-driven wobble keyed on a `uTime` uniform, so the
  scene has subtle idle motion even at scroll-rest (not fully static).

Lighting: one `DirectionalLight` + one `AmbientLight` (desktop). Mobile: `AmbientLight`
only, to cut a light pass.

## Scroll → animation data flow

- A `scroll` listener stores raw `window.scrollY` in a variable each event.
- The `requestAnimationFrame` render loop lerps an internal `smoothScroll` value toward
  the raw value every frame (prevents jank on fast/trackpad scrolling).
- `smoothScroll` drives, per mesh: a Y-position offset (different depth multiplier per
  mesh → parallax) and a shared slow Z-rotation.
- No external animation library (no GSAP/ScrollTrigger) — plain arithmetic into
  `mesh.position` / `mesh.rotation` each frame is sufficient for ~5 objects.

## Mobile branch

Single `matchMedia('(max-width: 768px)')` check at init time selects:

- Geometry segment count: 16 (mobile) vs 32 (desktop) for sphere/icosahedron.
- Light count: ambient-only (mobile) vs ambient+directional (desktop).

Same code path otherwise — per explicit user decision, no static-image fallback branch.

## Error handling

If WebGL context creation throws (old browser/webview), catch the Three.js
initialization error and replace the canvas with a CSS gradient using the same 4 brand
colors, so the hero text never sits on a blank/broken background.

## Out of scope

- No production integration into `prototype/` build pipeline.
- No automated tests — this is a disposable visual-review artifact. Manual check in
  desktop + mobile viewport (browser devtools) is the acceptance method.
- No real hero copy/CTA — placeholder text only, since content isn't the point of the
  demo.
