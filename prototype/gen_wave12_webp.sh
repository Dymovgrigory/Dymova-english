#!/bin/bash
# png (фотореалистичные, ~1448x1086) -> webp 896x512 (<400KB) для волны 12.
# Центральный кроп до пропорции 7:4, затем ресайз до 896x512.
cd "$(dirname "$0")/article-images"
for f in *.png; do
  slug="${f%.png}"
  out="${slug}.webp"
  [ -s "$out" ] && continue
  read w h <<< "$(sips -g pixelWidth -g pixelHeight "$f" | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w, h}')"
  # целевая пропорция 896:512 = 7:4
  th=$(( w * 4 / 7 ))   # высота кропа при полной ширине
  tw=$(( h * 7 / 4 ))   # ширина кропа при полной высоте
  if [ "$th" -le "$h" ]; then
    sips -c "$th" "$w" "$f" --out "${slug}-tmp.png" >/dev/null 2>&1
  else
    sips -c "$h" "$tw" "$f" --out "${slug}-tmp.png" >/dev/null 2>&1
  fi
  sips -z 512 896 "${slug}-tmp.png" >/dev/null 2>&1
  cwebp -q 82 "${slug}-tmp.png" -o "$out" >/dev/null 2>&1
  rm -f "${slug}-tmp.png"
  echo "$out $(stat -f%z "$out")"
done
