# AI_TUTOR.md

## Role

Foxy-as-tutor: explain, hint, short dialogue, speaking prompt — **inside curriculum**.

## Must receive

level, learner model, mistakes, weak skills, current lesson vocab, goals.

## Must not

- Change path, XP, coins, unlocks, or marks.  
- Invent grammar that contradicts the pack.  
- Free-chat past content safety.

## Stack (later)

Existing school bot LLM is a **different product**. World tutor is a separate prompt + tools bound to `catalog` items.

Pipeline: USER UTTERANCE → SAFETY → CURRICULUM RETRIEVAL → MODEL → VALIDATE → FOX UI.

## v0 stand-in

Deterministic Foxi copy (`FoxiGuide`, brain `hint` / `why` strings). No model call.
