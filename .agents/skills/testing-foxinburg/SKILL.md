---
name: testing-foxinburg
description: Test the Foxinburg (dymova-english.ru) Tilda custom blocks end-to-end. Use when verifying HTML/CSS/JS prototype rendering, emoji replacements, responsive layout, or combined page assembly.
---

# Testing Foxinburg Custom Blocks

## Overview

The Foxinburg site uses custom HTML/CSS/JS blocks inserted into Tilda via T123 "HTML-code" blocks. Individual block files are HTML fragments (no DOCTYPE, no `<meta charset>`) designed to be pasted into Tilda. Testing must account for this.

## Prerequisites

- Repo cloned: `Dymova-english/` with `prototype/` directory containing HTML block files
- Python 3 available for HTTP server
- Chrome browser available

## Devin Secrets Needed

- None required for local prototype testing
- `TILDA_PASSWORD` needed only if uploading to Tilda (not for local testing)

## Setup

1. **Start HTTP server** (required for proper UTF-8 rendering):
   ```bash
   cd /path/to/Dymova-english/prototype
   python3 -m http.server 8080 &
   ```
   Do NOT use `file:///` URLs — Chrome may mangle filenames with underscores and the HTML fragments lack charset declarations.

2. **Use test_wrapper.html** for testing individual blocks:
   The `test_wrapper.html` file fetches and injects block HTML files with proper `<meta charset="UTF-8">`. Open `http://localhost:8080/test_wrapper.html` to see header + directions + team + languages blocks rendered together with correct encoding.

3. **Use main_combined_v5.html** (or latest version) for full-page testing:
   This file concatenates all blocks. It will show mojibake when opened directly in browser (expected — it's a Tilda fragment). Verify block presence via DOM inspection rather than visual text.

## Test Categories

### 1. Visual Rendering Tests
- **Seamless gradients**: Check for visible `border-bottom` lines between sections. Use browser inspector to verify no borders.
- **SVG icons vs emoji**: Look for unicode emoji characters (bear, backpack, rocket, fox, play triangle, flags). They should be replaced with SVG elements or `<img>` tags.
- **Brand assets**: Verify `fox-head-yellow.png` loads from GitHub raw URLs. Check for broken image icons.
- **Text badges**: Language flags should be text pills ("DE", "CN") not emoji flags.

### 2. Interactive Tests
- **Navigation dropdowns**: Click dropdown buttons, verify panels appear with white background and correct links.
- **FAQ accordion**: Click questions, verify answers expand/collapse.
- **Burger menu**: Resize to 375px width, verify burger icon appears and toggles nav.

### 3. Responsive Tests
- **Mobile viewport**: Resize browser to ~375px width. On Linux, use:
  ```bash
  wmctrl -r :ACTIVE: -b remove,maximized_vert,maximized_horz
  sleep 0.5
  xdotool getactivewindow windowsize 375 768
  ```
- **Verify**: Burger icon visible, desktop nav hidden, content reflows.
- **Known issue**: Mobile nav drawer positioning might use `top: 100%` of parent which pushes it below the hero. Check `top` value on `.fxb-nav.fxb-open` — it should anchor to the topline height, not the full hero height.

### 4. Combined File Integrity
- Open combined file and verify all block IDs exist in DOM:
  ```javascript
  ['fxb-hero','fxb-enrollment','fxb-onboarding','fxb-pbhead','fxb-gallery',
   'fxb-dir','fxb-team','fxb-lang','fxb-adv','fxb-pricing','fxb-faq',
   'fxb-sved','fxb-contacts','fxb-footer'].forEach(id => {
    var el = document.getElementById(id);
    console.log(id + ': ' + (el ? 'OK h=' + el.getBoundingClientRect().height : 'MISSING'));
  });
  ```

## Common Pitfalls

- **Encoding**: Always use HTTP server, never `file:///`. Individual HTML files are fragments without charset meta tags.
- **Chrome URL mangling**: Chrome address bar may strip underscores from `file:///` URLs (e.g., `tilda_header_unified.html` becomes `tildaheader_unified`). HTTP server avoids this.
- **window.resizeTo()**: May not work on maximized windows. Use `wmctrl` + `xdotool` for reliable window resizing.
- **DevTools mobile toggle**: Might be hard to interact with via automation. Prefer actual window resize over DevTools device toolbar.
- **Brand assets**: Images load from `https://raw.githubusercontent.com/Dymovgrigory/Dymova-english/devin/1782590824-session6-redesign/brand-assets/`. If branch changes, URLs may break.

## Reporting

- Post ONE comment on the PR with test results
- Use `<details>/<summary>` tags to collapse sections
- Include screenshots for key assertions
- Flag any emoji characters still visible as high-priority issues
- Note encoding issues in combined file as "expected" (Tilda provides charset)
