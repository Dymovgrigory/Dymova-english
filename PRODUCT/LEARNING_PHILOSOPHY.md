# LEARNING_PHILOSOPHY.md

## Outcome over engagement

A child who speaks one new phrase correctly is more successful than a child who farmed 500 XP.

Rewards exist to **support** DISCOVER → LEARN → PRACTICE → MASTER. They never replace it.

## How Foxinburg teaches (v1 live)

1. **Oral first** — starter course is spoken English (echo / listen / match), then phonics.  
2. **Teach, then check** — lesson items include explain + word/phrase cards before graded challenges.  
3. **Server grades value** — typed / MCQ answers are scored on the backend; speaking UX is client (Web Speech) but XP is not minted from a self-reported “I said it.”  
4. **Mistakes become practice** — `mistakes` + `word_stats` feed the Training Yard.  
5. **Spaced return** — Leitner-style strength 0–5 in `srs.py`; due words become Review Quest.

## Principles

| Principle | Meaning |
|---|---|
| Retrieval > re-reading | Challenges force production, not only recognition |
| Small new + lots of recycle | New items mixed with due / weak items |
| Immediate feedback | Correct / incorrect state per challenge |
| Explain why | Theory cards + Foxi pose, not a dump of glossary |
| Mastery unlocks world | Stars + unit stickers, not arbitrary map cosmetics |
| Shame-free | Heart loss is a world event, not a scold |

## What we refuse

- Casino loops (watch-ad, infinite spin, pay-to-skip learning).  
- Frontend-trusted completion.  
- “Continue” with no reason. Next Best Action must say **why**.  
- Content hardcoded only in React. Catalog lives in Python packs (`starter_course.py`, `phonics_course.py`) until CMS.

## Skills model (target)

Vocabulary item · Grammar concept · Skill (listen / speak / read / write) · Confidence.

Fox Brain classifies each as mastered / unstable / forgotten / new. The next lesson is a function of that model, not a static list.
