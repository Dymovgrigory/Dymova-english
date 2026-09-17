# CONTENT_ENGINE.md

## Current

Content is Python packs, not CMS:

- `starter_course.py` — oral year-1  
- `phonics_course.py` — letters / SATPIN  
- `word_library.py` + image paths  
- `catalog.py` assembles units → lessons → items  

Frontend must not hardcode answer keys. Public lesson items strip `correct_index`.

## Target entities (CMS)

Course → Unit → Chapter → Lesson → Challenge → Question / Hint / Explanation  
Vocabulary · GrammarConcept · Skill  
Audio · Image · Video · Dialogue · Scenario  

Reusable: one vocab item in lesson, review, sprint, dialogue, quest, test.

## Versioning

`content_pack` + `content_version`. Player sessions pin the pack they started so a publish does not orphan an active session.

## Admin

Until CMS: editors change Python packs + tests (`test_world_learn.py` catalog volume). After: Admin/CMS CRUD with preview + publish.

## Safety

AI-generated items must pass CONTENT VALIDATION + curriculum rules. AI cannot mutate the live pack.
