# Контракт этапа 5: чтение и все навыки (reading nodes)

Зафиксировано 2026-09-19. Все исполнители этапа 5 работают строго по этому
контракту — отступления только через оркестратора.

## Правовая рамка (критично)

- Тексты — АВТОРСКИЕ, написанные для платформы. Нельзя брать тексты, диалоги,
  песни и упражнения учебника Spotlight, нельзя использовать имена его
  персонажей (Larry, Lulu, Nanny Shine, Chuckles и др.). Герой — Foxy.
- См. `world-backend/content/spotlight/REVIEW.md`.

## Модель данных (world-backend/app/learning/content.py)

```python
class TextQA(BaseModel):
    id: str                      # "{text_id}.q1"
    kind: Literal["choice", "truefalse", "gap"]
    q_en: str                    # вопрос/предложение простым английским
    q_ru: str                    # перевод-подсказка для ребёнка
    options: list[str] = []      # choice: 3 варианта; gap: 3 слова; truefalse: []
    answer: str                  # choice/gap: точная строка из options; truefalse: "true"/"false"

class Text(BaseModel):
    id: str                      # "{module_id}.t1" (например "sp2.m1.t1")
    title_en: str
    title_ru: str
    body_en: str                 # 3–6 коротких предложений
    questions: list[TextQA]      # 4–5 шт., минимум по одному choice и truefalse
```

- `Module.texts: list[Text] = []`
- `Node.text_id: str | None = None`
- `NodeKind` += `"reading"`

## Лексическое правило

Каждый токен `body_en` и `q_en` обязан быть либо словом из `words` текущего или
прошлых модулей ТОГО ЖЕ учебника (проверка через существующий
`is_taught(token, known)` — учитывает стемы), либо словом из `FUNCTION_WORDS`.
Числительные и собственные имена Foxy/Foxinburg разрешены. Валидатор курса
(`validate()`) падает с понятной ошибкой на неизвестном слове.

## Задания (world-backend/app/learning/challenges.py)

`Challenge.public()` отдаёт `{index, type, atom_id, graded, ...prompt}`.

1. `read_text` — **неоцениваемый** (graded=false) первый шаг сессии чтения:
   `{text_id, title_en, title_ru, sentences: string[]}` (body_en разбит на
   предложения для TTS-подсветки).
2. `read_text_truefalse` — `{text_id, sentence_en, q_ru}`, ответ `{"answer": bool}`,
   solution `{"answer": bool}`.
3. `read_text_answer` — `{text_id, q_en, q_ru, options: string[]}`,
   ответ `{"index": int}`, solution `{"index": int}`.
4. `word_in_context` — `{text_id, sentence_en}` где на месте слова «___»,
   `options: string[]` (3 слова, верное — из активной лексики модуля),
   ответ `{"index": int}`, solution `{"index": int}`.

`atom_id` у всех заданий чтения — `text_id` текста.

## Сессия чтения (builder.py)

- `build_session` для узла kind="reading": `_reading_session` →
  `[read_text(неоцен.), 4–5 заданий по вопросам текста]` + обычный `_mix_due`.
  Порядок через `_spread` (read_text неоцениваемый — уходит первым).
- Проверка ответов: `checker.check_choice` для choice/gap, bool-сравнение для
  truefalse (добавить `check_bool`).

## Расстановка узлов в модулях

В каждый модуль sp1–sp4 добавляется ОДИН узел `{ "id": "{module}.n<K>",
"kind": "reading", "text_id": "{module}.t1" }` (K — следующий свободный номер).
Позиция: перед узлом "chest"; если chest нет — перед "review". Существующие
id узлов не меняются (прогресс игроков привязан к id).

## Фронтенд (world/)

- Рендереры четырёх новых типов в движке заданий. `read_text`: «книжный
  разворот» на материале `mat-parchment` (дизайн-токены проекта), кнопка
  «Слушать» — TTS с подсветкой текущего предложения/слова (использовать
  существующую TTS-инфраструктуру слов), кнопка «Я прочитал(а)».
  Вопросные типы показывают текст свернутым/доступным («Показать текст»).
- Узел reading на тропе: иконка-книжка, подпись «Читаем».
- Шильдики навыков на заданиях в сессии: маппинг тип → навык:
  listen_* → «Слушаем», speak → «Говорим», spell_tiles/type_word/build_phrase/
  listen_build → «Пишем», read_* / word_in_context → «Читаем»,
  grammar_pick/teach_rule → «Грамматика», остальные словные → «Слова».
- Доступность: тач-цели ≥40px, aria у диалога текста, работа без звука.

## REVIEW.md

Дополнить чек-лист преподавателя: текст модуля читается ребёнком этого класса
за ~1 минуту; все слова пройдены; вопросы однозначны; ответ проверяется по
тексту. Отметить в таблице статусов колонку «Тексты».
