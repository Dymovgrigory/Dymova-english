# EXPERIMENTS.md

## Status

Not shipped. Do not A/B learning integrity (answer keys, pass thresholds) without a review.

## Schema (target)

`experiment_id`, `variant`, `audience`, `feature_flag`, `start`, `end`, `primary_metric`.

Safe tests: button copy, lesson length (item count cap), reward **copy** (not amounts without economy review), quest frequency, reminder timing, HUD composition.

## Rule

Assignment is server-side. Client only renders `variant` from ScreenDefinition / home payload.

Learning outcome metrics must not degrade beyond a pre-registered stop rule.
