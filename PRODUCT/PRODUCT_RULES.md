# PRODUCT_RULES.md

A feature ships only if it answers **at least one**:

1. Helps learn?  
2. Helps understand progress?  
3. Motivates fairly?  
4. Makes the world feel alive?  
5. Connects systems?  
6. Yields useful data?  
7. Strengthens personalization?  

## Hard rules

- LEARNING OUTCOME > ENGAGEMENT METRIC.  
- Frontend is never source of truth for XP, coins, inventory, completion, league.  
- Every balance change is a ledger row with idempotency.  
- UI *is* world when the object can exist in Foxinburg; otherwise a light HUD.  
- Mobile is a separate composition.  
- Strings: RU/EN, no hardcoded-only copy in random components long-term.  
- Stable analytic IDs on primary actions.  
- Do not destroy the working learn loop to chase 3D.

## Quality bar (not done if)

Pretty UI + fake backend · buttons no-op · refresh loses progress · duplicate rewards · world is a wallpaper · generic SaaS cards · no tests · no constraints.
