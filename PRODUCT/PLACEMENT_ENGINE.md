# PLACEMENT_ENGINE.md

## Status

**Specified, not shipped.** v1 course always starts at `family-L1` (starter oral).

## Goal

Adaptive placement → **Personal Learning Profile** → starting path.

## Skills to sample

Vocabulary · grammar · listening · reading · speaking (where device allows).

## Design

- Short (8–12 items), adaptive: 2 wrong in a band → stop band.  
- No coins for placement (integrity). Optional cosmetic “Foxy learned your path.”  
- Result stored as `user_skill` rows + `placement_version`.  
- Re-place only on parent/teacher request or after long inactivity.

## Output

`starting_unit_id`, CEFR-ish band (pre-A1 … A2 for this product), weak/strong tags for Fox Brain.

## Constraint

Placement cannot unlock paid school CRM groups. World placement ≠ school diagnostic booking.
