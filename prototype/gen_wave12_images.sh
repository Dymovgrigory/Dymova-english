#!/bin/bash
# Генерация 30 фирменных фотореалистичных иллюстраций с РЕАЛЬНЫМ маскотом
# бренда (референс «Маскот Фоксинбург.PNG» подмешивается скриптом
# /tmp/img_edit_gen.mjs через endpoint images/edits, модель gpt-image-2).
# Идемпотентно: пропускает уже существующие непустые png.
set -a; source ~/.kimi-code/.env; set +a
cd "$(dirname "$0")"

PRE="Photorealistic cinematic photo scene: this exact fox mascot character (keep his exact design: orange fox kid, big blue eyes, yellow t-shirt, purple shorts, purple backpack and sneakers)"
POST="bright modern real location, warm light, shallow depth of field, high detail. No text, no letters."

gen() { # $1=slug $2=scene
  local slug="$1"; local scene="$2"
  local out="article-images/${slug}.png"
  [ -s "$out" ] && { echo "SKIP $slug"; return 0; }
  for attempt in 1 2 3; do
    if node /tmp/img_edit_gen.mjs "$PRE $scene, $POST" "$out" >/dev/null 2>&1 && [ -s "$out" ]; then
      echo "OK $slug (попытка $attempt)"; return 0
    fi
    sleep 5
  done
  echo "FAIL $slug"; return 1
}

gen novosti-komu-nuzhen-repetitor-po-anglijskomu-5-priznakov "sitting one-on-one with a teenage student at a cozy table with an open workbook and pencils, explaining an exercise in a real tutoring room"
gen preparation "playing with a preschooler kid with colorful alphabet blocks and a small backpack on a classroom rug, school readiness theme"
gen repetitor "explaining a workbook exercise to a focused schoolboy at a wooden desk in a warm real study room with bookshelves"
gen blog-kak-vybrat-shkolu-anglijskogo-v-dolgoprudnom "standing with a parent and a child looking at a checklist clipboard in front of a small modern school building entrance"
gen blog-podgotovka-k-shkole-v-dolgoprudnom-obzor "waving at the entrance of a bright kindergarten school door while happy preschool kids with backpacks walk in"
gen blog-my-level-uchebniki "sitting at a desk next to a stack of colorful modern English textbooks and workbooks, reading one of them"
gen blog-present-simple-detyam "pointing at a big round wall clock and a daily routine chart with morning breakfast and school bag on a table nearby"
gen blog-vozrast-na-anglijskom "celebrating with kids around a birthday cake with candles and colorful number-shaped balloons in a decorated classroom"
gen blog-probely-po-anglijskomu-3-klass "placing a large jigsaw puzzle piece together with a small third-grade kid at a classroom table"
gen blog-probely-po-anglijskomu-6-klass "and a middle-school kid placing the last glowing puzzle piece into a big open-book-shaped jigsaw puzzle"
gen blog-probely-po-anglijskomu-8-klass "climbing wooden stairs together with a teenage student, filling one missing step with a glowing puzzle piece"
gen blog-probely-po-anglijskomu "repairing a ladder of books where one rung is missing, holding a small toolbox, curious kids watching"
gen blog-oge-za-god "marking a big wall calendar with twelve monthly pages with a pencil, a graduation cap lying on the desk"
gen blog-struktura-oge-po-anglijskomu "presenting four objects on a table in a row: headphones, an open book, a pen on paper and a speech-bubble-shaped cushion"
gen blog-kogda-nachinat-gotovitsya-k-oge "standing at a starting line with a small flag and a wall calendar, a teenager with a backpack ready to run beside him"
gen blog-bally-ege-anglijskij "celebrating a high score next to a rising bar chart made of wooden blocks with stars and a graduation cap on top"
gen blog-esse-ege-anglijskij "reading a handwritten essay draft at a desk with an ink pen and paper, warm lamp light"
gen blog-vpr-po-anglijskomu-4-klass "giving a thumbs up next to a small fourth-grade kid holding a school worksheet with checkmarks and a pencil"
gen blog-chto-takoe-vpr "explaining a school test paper to curious kids sitting at desks in a bright classroom"
gen blog-kak-nauchit-rebenka-chitat-po-anglijski "reading a big open picture book together with a small child sitting on a cozy rug"
gen blog-multfilmy-na-anglijskom-po-vozrastam "sitting among kids on a sofa watching a cartoon on a TV screen with popcorn bowls"
gen blog-pesni-na-anglijskom-dlya-detej "conducting like a choir leader while kids sing, musical notes decorations on the wall"
gen blog-kak-vyuchit-anglijskie-slova-bystro "dealing colorful flashcards to a smiling kid at a table, flashcards flying in the air"
gen blog-rebenok-ne-ponimaet-anglijskij-v-shkole "gently helping a puzzled schoolboy at a school desk with an open book"
gen blog-repetitor-ili-gruppa "standing in the middle of a room between a single student at a desk on one side and a small group of kids at a round table on the other"
gen blog-skolko-stoit-anglijskij-dlya-rebenka "counting coins next to a piggy bank and an open workbook on a wooden table"
gen novosti-so-skolki-let-uchit-anglijskij "standing on growth steps together with kids of increasing age from toddler to teenager"
gen novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat "standing between two friendly open doors, one showing a classroom and the other a cozy home study"
gen novosti-anglijskij-dlya-vzroslyh-s-nulya-s-chego-nachat "acting as a teacher showing first steps on a small whiteboard to an adult student with a notebook and coffee at a desk"
gen blog-kitajskij-dlya-detej "holding a red paper lantern with bamboo branches nearby while kids play with a folding fan"
echo DONE
