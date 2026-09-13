# world-pipeline — ассет-пайплайн Foxinburg World

Поток (§35/§221 брифа): концепт (Gemini image / вручную) → Meshy text-to-3d
(preview → refine) → gltf-transform (draco + webp 512) → `asset-registry.json`
→ (позже) CDN.

## Генерация нового ассета

```bash
python3 meshy_asset.py --id library-book-portal \
  --prompt "..." --texture-prompt "..." --category portals
```

Ключи — в `.env` (не коммитится). Баланс Meshy: `curl -H "Authorization: Bearer $MESHY_API_KEY" https://api.meshy.ai/openapi/v1/balance`.

## Ассеты

| id | категория | размер | источник |
|---|---|---|---|
| school-foxcoin | collectibles | 182 КБ | Meshy (preview 20 кр + refine 10 кр) |

`asset-registry.json` — единый реестр (§52): id, url, thumbnail, lod,
variants, sizeKb, source. `preview/foxcoin.html` — тестовый viewer
(`python3 -m http.server` из корня world-pipeline → /preview/foxcoin.html).

## Концепт-арт

Генерируется через AI-прокси (см. skill ai-image-gen):
`node ~/.kimi-code/bin/ai-image.mjs "<prompt>" --model gpt-image-2 --out ../generated/world/<name>.png`
(nano-banana-2 = Gemini image, нестабилен на прокси; gpt-image-2 — основной).
Готовое: `generated/world/school-hub-concept-v1.png` (School Hub, в бренде).
