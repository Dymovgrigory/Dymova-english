# Очередь генерации Meshy (продолжить с новым ключом)

Ключ — `secrets/meshy.env`. Модель и промпты не менять (STYLE_LOCK).

## Готово (2026-09-17)
Все слова Spotlight 1–4 в стиле «живой миниатюры», 30 этажей, 4 башни классов, фоны, спрайты.

## 1. Переделать эмоции (детские фигурки вместо каменных голов, ~24 кр.)
```bash
python3 world-pipeline/diorama_art.py words:sp4.m5 --budget --force --only word-bored word-angry word-scared word-tired
```

## 2. Замок — башни классов без фона как здания (~36 кр.)
