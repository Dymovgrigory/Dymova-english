# Очередь генерации Meshy

Ключ — `secrets/meshy.env`. Модель и промпты не менять (STYLE_LOCK). Качество — модель flare (без `--budget`).

## Готово (2026-09-17)
Все слова Spotlight 1–4, эмоции SP4, 30 этажей, 4 башни классов, фоны, спрайты окон.

## Замок (отложено владельцем, продолжить по команде)
Уже сгенерировано в `world/public/content/castle/`: сцены (wide/tall), башни классов без фона (sp1–sp4),
здания и интерьеры school, shop, glory. Осталось (~90 кр.): lexicon, stickers, yard, quests, nest (здание + интерьер).
```bash
python3 world-pipeline/diorama_art.py castle   # готовые пропустит
```
Интерфейс Замка ещё не переделан (сейчас старый `CastleHub`).
