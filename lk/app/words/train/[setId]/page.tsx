"use client";

// Тренажёр слов по методике Cambridge English for Young Learners (Starters / Movers / Flyers):
// слово вводится через картинку, звук и предложение-пример, а не парой «слово — перевод».
// Урок идёт по схеме «знакомство → узнавание → тренировка → применение»; ошибки возвращаются в конце.
// Задания повторяют форматы экзамена: Listen and choose, Look and read (tick / cross),
// Read and complete, Look and spell, Look and write, Say it, Match.
// Режимы (?mode=): classic — урок целиком; listen — на слух; spell — правописание;
// sprint — 60 секунд на скорость; cards — карточки.
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Coins, Ear, Languages, Mic, RotateCcw, Scroll, Shield, Snail, Timer, Volume2, VolumeX, X, Zap } from "lucide-react";
import CabinetPage from "@/components/cabinet-page";
import WordArt from "@/components/word-art";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, GameStats, PoolWord, Training, WordCard } from "@/lib/api";
import { isMuted, setMuted, sfx, speak } from "@/lib/sound";
import { celebrate } from "@/lib/fx";

export default function TrainPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = use(params);
  return (
    <CabinetPage bare>
      <Trainer setId={Number(setId)} />
    </CabinetPage>
  );
}

type Mode = "classic" | "listen" | "spell" | "sprint" | "cards";
type Word = WordCard & { text_ru: string };
type Kind = "intro" | "listen_img" | "listen_word" | "read_img" | "tick" | "gap" | "spell" | "missing"
  | "write" | "speak" | "match" | "flash";
type Step = {
  kind: Kind; word: Word; graded: boolean; retry?: boolean;
  options?: PoolWord[]; letters?: string[]; pairs?: Word[];
  sentence?: string; truth?: boolean; masked?: string; letterOpts?: string[]; answerLetter?: string;
};
type Feedback = { ok: boolean } | null;

// Инструкции — как в заданиях Cambridge: по-английски, с подсказкой на русском.
const INSTR: Record<Kind, [string, string]> = {
  intro: ["Look, listen and say.", "Посмотри, послушай и повтори"],
  listen_img: ["Listen and choose the right picture.", "Послушай и выбери картинку"],
  listen_word: ["Listen and choose the word you hear.", "Послушай и выбери слово"],
  read_img: ["Read the word and choose the picture.", "Прочитай слово и выбери картинку"],
  tick: ["Look and read. Is it right or wrong?", "Посмотри и прочитай. Предложение подходит к картинке?"],
  gap: ["Read and choose the right word.", "Прочитай и выбери слово для пропуска"],
  spell: ["Look and spell the word.", "Собери слово из букв"],
  missing: ["Find the missing letter.", "Найди пропущенную букву"],
  write: ["Look and write the word.", "Напиши слово по-английски"],
  speak: ["Listen and say the word.", "Послушай и скажи слово"],
  match: ["Match the words and the pictures.", "Соедини слова и картинки"],
  flash: ["Remember the word. Then turn the card.", "Вспомни слово и переверни карточку"],
};
const HINT_KEY = "lk_ru_hints";

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
const pick = <T,>(a: T[]) => a[Math.floor(Math.random() * a.length)];
const hasImg = (src?: string) => !!src && !src.startsWith("/wimg/");
const buildable = (en: string) => /^[a-z' -]{2,11}$/i.test(en);
const norm = (s: string) => s.toLowerCase().replace(/[^a-z' ]/g, "").replace(/\s+/g, " ").trim();
const SR = () => (typeof window !== "undefined"
  ? ((window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }).SpeechRecognition
    || (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition) : undefined);

/** Где в предложении стоит слово (с окончаниями -s, -es, -ed, -ing). */
function locate(sentence: string, word: string): { a: string; m: string; b: string } | null {
  if (!sentence || !word) return null;
  const esc = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(^|[^A-Za-z])(${esc}(?:s|es|d|ed|ing)?)(?![A-Za-z])`, "i");
  const m = re.exec(sentence);
  if (!m) return null;
  const start = m.index + m[1].length;
  return { a: sentence.slice(0, start), m: m[2], b: sentence.slice(start + m[2].length) };
}
const canGap = (w: { text_en: string; example_en?: string }) => !!locate(w.example_en ?? "", w.text_en);
const asPool = (w: Word): PoolWord => ({ id: w.id, text_en: w.text_en, text_ru: w.text_ru, image_url: w.image_url, example_en: w.example_en });

// Слова, которые нельзя ставить рядом как варианты: синонимы и картинки, где видно одно и то же
// (на фото «son» есть и папа, на «face» — рот и нос). Иначе у задания два правильных ответа.
const CONFUSE: string[][] = [
  ["mum", "mother", "dad", "father", "parent", "family", "son", "daughter", "child", "kid", "baby", "boy", "girl", "brother", "sister", "twins",
    "grandma", "grandmother", "granny", "grandpa", "grandfather", "granddad", "grandparent", "grandchild", "grandson", "granddaughter",
    "man", "woman", "lady", "person", "people", "adult", "husband", "wife", "uncle", "aunt", "cousin", "friend", "best friend", "neighbour", "guest", "teenager"],
  ["face", "mouth", "lip", "teeth", "tooth", "nose", "eye", "cheek", "chin", "tongue", "head", "hair", "ear"],
  ["hand", "finger", "arm", "skin"], ["leg", "knee", "foot", "feet", "toe", "ankle"], ["body", "chest", "belly", "stomach", "back"],
  ["bike", "bicycle", "cycling"], ["tv", "television", "screen"], ["cookie", "biscuit"], ["chips", "fish and chips", "crisps"],
  ["burger", "hamburger", "fast food"], ["lorry", "truck"], ["subway", "underground"], ["film", "movie", "cinema"], ["present", "gift", "surprise"],
  ["sweet", "candy", "chocolate"], ["shop", "store", "supermarket", "market"], ["sea", "ocean", "beach", "seaside", "coast", "shore"],
  ["kitten", "cat", "pet"], ["puppy", "dog", "pet"], ["food", "meal", "dinner", "lunch", "breakfast", "supper", "picnic"],
  ["fruit", "food", "snack", "dessert", "apple", "banana", "orange", "pear", "grape", "peach", "melon", "watermelon", "lemon", "cherry", "strawberry", "pineapple"],
  ["vegetable", "food", "meal", "carrot", "potato", "tomato", "onion", "pea", "bean", "pepper", "corn", "garlic", "salad", "mushroom"],
  ["drink", "water", "juice", "milk", "tea", "coffee", "lemonade", "cola", "mineral water", "soft drink"],
  ["animal", "insect", "bug", "creature"], ["bird", "robin", "owl", "parrot", "duck", "chicken"],
  ["house", "home", "flat", "apartment", "building"], ["clothes", "shirt", "t-shirt", "jumper", "sweater"],
  ["sun", "sunny", "sunshine", "sunlight", "summer", "hot", "shine"], ["rain", "rainy", "wet", "umbrella"], ["snow", "snowy", "winter", "cold"],
  ["sport", "football", "soccer", "ball"], ["phone", "mobile phone", "smartphone", "mobile", "telephone"], ["computer", "laptop"],
];
const GROUP = new Map<string, number[]>();
CONFUSE.forEach((g, i) => g.forEach((w) => GROUP.set(w, [...(GROUP.get(w) ?? []), i])));
const confusable = (a: string, b: string) => {
  const ga = GROUP.get(a.toLowerCase()) ?? [];
  const gb = GROUP.get(b.toLowerCase()) ?? [];
  return ga.some((g) => gb.includes(g));
};

let FAR: PoolWord[] = []; // слова из других тем (приходят с сервера)

/** Варианты ответа. strict — без похожих слов; onlyFar — только из других тем (для пропусков). */
function options(word: Word, pool: PoolWord[], needImg: boolean, strict = needImg, onlyFar = false): PoolWord[] {
  const ok = (p: PoolWord) => p.id !== word.id && norm(p.text_en) !== norm(word.text_en)
    && (!strict || !confusable(p.text_en, word.text_en))
    && (!needImg || (hasImg(p.image_url) && p.image_url !== word.image_url));
  const own = onlyFar ? [] : shuffle(pool.filter(ok)).slice(0, 3);
  const seen = new Set(own.map((p) => norm(p.text_en)));
  const far = shuffle(FAR.filter((p) => ok(p) && !seen.has(norm(p.text_en)))).slice(0, 3 - own.length);
  return shuffle([asPool(word), ...own, ...far]);
}

function makeStep(kind: Kind, w: Word, pool: PoolWord[], graded = true): Step {
  const st: Step = { kind, word: w, graded };
  if (kind === "spell") st.letters = shuffle([...w.text_en.toLowerCase().replace(/ /g, "␣")]);
  if (kind === "listen_word") st.options = options(w, pool, false);
  if (kind === "gap") {
    // в пропуск не должно подходить другое слово из вариантов (mum / dad, cookie / biscuit)
    st.options = options(w, pool, false, true, true);
    if (st.options.length < 3) st.options = options(w, pool, false, true);
  }
  if (kind === "listen_img" || kind === "read_img") {
    st.options = options(w, pool, true);
    // мало непохожих картинок (например, тема «Семья») — тогда задание на слух со словами
    if (st.options.length < 3) return makeStep(canGap(w) ? "gap" : "listen_word", w, pool, graded);
  }
  if (kind === "tick") {
    // Как в Starters, Reading Part 1: картинка и предложение — подходит или нет.
    // неверное предложение берём из другой темы — чтобы оно точно не подходило к картинке
    const fit = (p: PoolWord) => p.id !== w.id && canGap(p) && !confusable(p.text_en, w.text_en) && !locate(p.example_en ?? "", w.text_en);
    const other = shuffle(FAR.filter(fit))[0] ?? shuffle(pool.filter((p) => fit(p) && hasImg(p.image_url)))[0];
    st.truth = !other || Math.random() < 0.5;
    st.sentence = st.truth ? w.example_en : other!.example_en;
  }
  if (kind === "missing") {
    const letters = [...w.text_en.toLowerCase()];
    const idxs = letters.map((c, i) => (/[a-z]/.test(c) ? i : -1)).filter((i) => i >= 0);
    const at = pick(idxs.length > 2 ? idxs.slice(1) : idxs);
    st.answerLetter = letters[at];
    st.masked = letters.map((c, i) => (i === at ? "_" : c)).join("");
    const abc = "aeioubcdfghklmnprstwy".split("").filter((c) => c !== st.answerLetter);
    st.letterOpts = shuffle([st.answerLetter, ...shuffle(abc).slice(0, 3)]);
  }
  return st;
}

function plan(tr: Training, mode: Mode): Step[] {
  FAR = tr.pool_far ?? [];
  const words: Word[] = tr.cards.map((c) => ({ ...c, text_ru: tr.answers[c.id] ?? "" }));
  const pool: PoolWord[] = tr.pool && tr.pool.length >= 4 ? tr.pool : words.map(asPool);
  const imgPool = pool.filter((p) => hasImg(p.image_url)).length >= 4;
  const canSpeak = !!SR();
  const img = (w: Word) => hasImg(w.image_url) && imgPool;
  const isNew = (w: Word) => w.strength === null || w.strength === undefined;
  // Узнавание (receptive) → тренировка → применение (productive): по силе слова.
  const recognise = (w: Word): Kind => pick<Kind>(img(w) ? ["listen_img", "read_img", "tick"] : canGap(w) ? ["gap", "listen_word"] : ["listen_word"]);
  const practise = (w: Word): Kind => pick<Kind>([
    ...(canGap(w) ? ["gap" as Kind] : []), ...(img(w) ? ["tick" as Kind] : []), "missing", "listen_word"]);
  const produce = (w: Word): Kind => pick<Kind>([
    ...(buildable(w.text_en) ? ["spell" as Kind] : []), ...(img(w) || canGap(w) ? ["write" as Kind] : []),
    ...(canSpeak ? ["speak" as Kind] : []), "missing"]);
  const byStrength = (w: Word): Kind => {
    const s = w.strength ?? 0;
    return s <= 1 ? recognise(w) : s <= 3 ? practise(w) : produce(w);
  };

  if (mode === "cards") return shuffle(words).map((w) => ({ kind: "flash" as Kind, word: w, graded: true }));
  if (mode === "sprint") {
    return shuffle([...words, ...words]).map((w) => makeStep(
      pick<Kind>([...(img(w) ? ["tick", "read_img"] as Kind[] : []), ...(canGap(w) ? ["gap" as Kind] : []), "listen_word"]), w, pool));
  }
  if (mode === "listen") {
    return shuffle(words).map((w) => makeStep(img(w) ? pick<Kind>(["listen_img", "listen_word"]) : "listen_word", w, pool));
  }
  if (mode === "spell") {
    return shuffle(words).map((w) => makeStep(pick<Kind>([
      ...(buildable(w.text_en) ? ["spell" as Kind] : []), "missing", ...(img(w) || canGap(w) ? ["write" as Kind] : [])]), w, pool));
  }

  const steps: Step[] = [];
  const fresh = words.filter(isNew);
  const review = words.filter((w) => !isNew(w));
  // 1. Знакомство: по два слова — картинка, звук, предложение; сразу узнавание.
  for (let i = 0; i < fresh.length; i += 2) {
    const pair = fresh.slice(i, i + 2);
    pair.forEach((w) => steps.push({ kind: "intro", word: w, graded: false }));
    shuffle(pair).forEach((w) => steps.push(makeStep(img(w) ? pick<Kind>(["listen_img", "read_img"]) : "listen_word", w, pool)));
  }
  // 2. Тренировка новых слов в контексте.
  shuffle(fresh).forEach((w) => steps.push(makeStep(practise(w), w, pool, false)));
  // 3. Повторение: задание по силе слова.
  shuffle(review).forEach((w) => steps.push(makeStep(byStrength(w), w, pool)));
  // 4. Применение: написать или сказать новые слова.
  shuffle(fresh).slice(0, 4).forEach((w) => steps.push(makeStep(produce(w), w, pool, false)));
  // 5. Итог: соединить слова и картинки.
  const pairWords = shuffle(words.filter(img)).slice(0, 5);
  if (pairWords.length >= 3) steps.push({ kind: "match", word: pairWords[0], graded: false, pairs: pairWords });
  return steps;
}

const PRAISE = ["Great!", "Super!", "Correct!", "Well done!", "Brilliant!", "Excellent!"];

function Trainer({ setId }: { setId: number }) {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active, refreshStats } = useCabinet();
  const [mode, setMode] = useState<Mode>("classic");
  const [tr, setTr] = useState<Training | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [idx, setIdx] = useState(0);
  const [fb, setFb] = useState<Feedback>(null);
  const [picked, setPicked] = useState<string | number | null>(null);
  const [combo, setCombo] = useState(0);
  const [score, setScore] = useState({ ok: 0, all: 0, coins: 0 });
  const [done, setDone] = useState<(GameStats & { bonus_coins: number; perfect: boolean }) | null>(null);
  const [error, setError] = useState("");
  const [muted, setMute] = useState(false);
  const [hints, setHints] = useState(true);
  const [left, setLeft] = useState(60);
  const reported = useRef(new Set<number>());
  const started = useRef(Date.now());

  useEffect(() => {
    setMute(isMuted());
    try { setHints(window.localStorage.getItem(HINT_KEY) !== "0"); } catch { /* по умолчанию подсказки есть */ }
    const m = new URLSearchParams(window.location.search).get("mode") as Mode | null;
    if (m && ["classic", "listen", "spell", "sprint", "cards"].includes(m)) setMode(m);
  }, []);

  useEffect(() => {
    if (!token || !active) return;
    api.startTraining(token, studentId, setId)
      .then((t) => { setTr(t); started.current = Date.now(); })
      .catch(() => setError(ru ? "Не получилось начать тренировку. Попробуйте ещё раз." : "Could not start. Try again."));
  }, [token, active, studentId, setId, ru]);

  useEffect(() => { if (tr) setSteps(plan(tr, mode)); }, [tr, mode]);

  const step = steps[idx];
  const progress = steps.length ? Math.round((idx / steps.length) * 100) : 0;
  const code = tr?.code ?? "";
  const topic = tr?.topic ?? "";

  const finish = useCallback(async () => {
    if (!token) return;
    sfx("done");
    celebrate(true);
    try {
      setDone(await api.wordFinish(token, studentId, setId, score.ok, score.all));
    } catch {
      setDone({ bonus_coins: 0, perfect: false } as GameStats & { bonus_coins: number; perfect: boolean });
    }
    void refreshStats();
  }, [token, studentId, setId, score, refreshStats]);

  useEffect(() => {
    if (mode !== "sprint" || !tr || done) return;
    const t = setInterval(() => setLeft((l) => {
      if (l <= 1) { clearInterval(t); setIdx(steps.length); void finish(); return 0; }
      return l - 1;
    }), 1000);
    return () => clearInterval(t);
  }, [mode, tr, done, steps.length, finish]);

  // Автоозвучка там, где задание начинается со слуха.
  useEffect(() => {
    if (!step || fb) return;
    if (["intro", "listen_img", "listen_word", "speak"].includes(step.kind)) {
      const t = setTimeout(() => void speak(token, step.word.text_en), 280);
      return () => clearTimeout(t);
    }
  }, [step, fb, token]);

  const next = useCallback(() => {
    setFb(null);
    setPicked(null);
    if (idx + 1 >= steps.length) { setIdx(steps.length); void finish(); }
    else setIdx(idx + 1);
  }, [idx, steps.length, finish]);

  const grade = useCallback(async (ok: boolean, kind: Kind) => {
    if (!step) return;
    sfx(ok ? "ok" : "bad");
    setFb({ ok });
    setCombo((c) => {
      const n = ok ? c + 1 : 0;
      if (n > 0 && n % 5 === 0) celebrate(false);
      return n;
    });
    if (step.graded) setScore((s) => ({ ...s, ok: s.ok + (ok ? 1 : 0), all: s.all + 1 }));
    if (!ok && !step.retry && mode !== "sprint") {
      // ошибка вернётся в конце урока заданием на узнавание
      const pool = tr?.pool ?? [];
      const w = step.word;
      const easier: Kind = hasImg(w.image_url) ? (kind === "listen_img" ? "read_img" : "listen_img") : canGap(w) && kind !== "gap" ? "gap" : "listen_word";
      setSteps((list) => [...list, { ...makeStep(easier, w, pool, false), retry: true }]);
    }
    if (step.graded && token && !reported.current.has(step.word.id)) {
      reported.current.add(step.word.id);
      const m = ["spell", "write", "missing"].includes(kind) ? "type" : ["listen_img", "listen_word"].includes(kind) ? "listen" : kind === "speak" ? "speak" : "";
      try {
        const r = await api.wordAnswer(token, studentId, step.word.id, ok, m, `word:${step.word.id}:step:${idx}:kind:${kind}`);
        if (r.coins) setScore((s) => ({ ...s, coins: s.coins + (r.coins ?? 0) }));
      } catch { /* тренировка продолжается */ }
    }
    if (mode === "sprint") setTimeout(() => { setFb(null); setPicked(null); setIdx((i) => i + 1); }, ok ? 450 : 1100);
  }, [step, token, studentId, tr, mode, idx]);

  function choose(o: PoolWord) {
    if (fb || !step) return;
    setPicked(o.id);
    void grade(o.id === step.word.id || norm(o.text_en) === norm(step.word.text_en), step.kind);
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!step) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "Enter" && (fb || step.kind === "intro") && tag !== "INPUT") { e.preventDefault(); next(); return; }
      if (!fb && step.options && /^[1-4]$/.test(e.key) && tag !== "INPUT") {
        const o = step.options[Number(e.key) - 1];
        if (o) choose(o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const toggleHints = () => {
    const v = !hints;
    setHints(v);
    try { window.localStorage.setItem(HINT_KEY, v ? "1" : "0"); } catch { /* не критично */ }
  };

  if (error) return <Center><p>{error}</p><a className="k-btn k-btn-go" href="/words">{ru ? "К словарям" : "Back"}</a></Center>;
  if (!tr) return <Center><div className="t-loading-mark" aria-hidden="true">✦</div><p>{ru ? "Собираем урок…" : "Preparing your lesson…"}</p></Center>;
  if (!steps.length) {
    return (
      <Center>
        <span className="t-big-ok"><Check size={64} strokeWidth={3} /></span>
        <h1>{ru ? "Все слова на сегодня повторены!" : "All words reviewed for today!"}</h1>
        <p>{ru ? "Возвращайся завтра или выбери другую тему." : "Come back tomorrow or pick another topic."}</p>
        <a className="k-btn k-btn-go k-btn-lg" href="/words">{ru ? "Выбрать тему" : "Pick a topic"}</a>
      </Center>
    );
  }
  if (done || idx >= steps.length) {
    const acc = score.all ? Math.round((score.ok / score.all) * 100) : 100;
    const mins = Math.max(1, Math.round((Date.now() - started.current) / 60000));
    return (
      <div className="t-wrap t-done">
        <div className="t-center">
          <motion.div className="t-complete-mark" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 220, damping: 14 }} aria-hidden="true">✦</motion.div>
          <h1>{done?.perfect ? "Perfect lesson!" : "Lesson complete!"}</h1>
          <p className="t-sub">{done?.perfect ? (ru ? "Без единой ошибки!" : "No mistakes!") : (ru ? "Урок пройден" : "Well done")}</p>
          <div className="t-results">
            {[
              ["xp", ru ? "Монеты" : "Coins", <><Coins size={24} strokeWidth={2.4} color="#D99A00" /> +{score.coins + (done?.bonus_coins ?? 0)}</>],
              ["acc", ru ? "Точность" : "Accuracy", `${acc}%`],
              ["time", ru ? "Время" : "Time", `${mins} ${ru ? "мин" : "min"}`],
            ].map(([k, label, val], i) => (
              <motion.div key={k as string} className={`t-res t-res-${k}`} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.25 + i * 0.12 }}>
                <span>{label}</span><b>{val}</b>
              </motion.div>
            ))}
          </div>
          {done?.rank && (
            <p className="t-streak"><Shield size={22} strokeWidth={2.4} />
              {done.rank.next_title
                ? (ru ? `${done.rank.title} · до звания «${done.rank.next_title}» ${done.rank.to - done.rank.learned} слов` : `${done.rank.title} · ${done.rank.to - done.rank.learned} words to “${done.rank.next_title}”`)
                : done.rank.title}
            </p>
          )}
          {done?.quest && (
            <p className="t-streak t-quest"><Scroll size={22} strokeWidth={2.4} />
              {ru ? "Задание дня: " : "Task of the day: "}{done.quest.title} — {done.quest.done ? (ru ? "выполнено! Забери награду на главной." : "done! Claim it on the home page.") : `${done.quest.progress} / ${done.quest.target}`}
            </p>
          )}
          <p className="t-sub">{ru ? "Монеты уже в кошельке Мира — трать их на свой замок." : "Coins are in your World wallet — spend them on your castle."}</p>
          <div className="t-done-actions">
            <a className="k-btn k-btn-go k-btn-lg" href={`/words/train/${setId}${mode !== "classic" ? `?mode=${mode}` : ""}`}><RotateCcw size={20} strokeWidth={2.6} />{ru ? "Ещё раз" : "Again"}</a>
            <a className="k-btn k-btn-light k-btn-lg" href={`/words/set/${setId}`}>{ru ? "Другой режим" : "Other mode"}</a>
            <a className="k-btn k-btn-light k-btn-lg" href="/words">{ru ? "К словарям" : "Word lists"}</a>
          </div>
        </div>
      </div>
    );
  }

  const w = step.word;
  const praise = PRAISE[(idx + combo) % PRAISE.length];
  const Say = ({ text = w.text_en, slow = false }: { text?: string; slow?: boolean }) => (
    <button className={"t-say" + (slow ? " t-say-slow" : "")} onClick={() => void speak(token, text, slow)} aria-label={slow ? (ru ? "Медленно" : "Slowly") : (ru ? "Послушать" : "Listen")}>
      {slow ? <Snail size={22} strokeWidth={2.4} /> : <Volume2 size={24} strokeWidth={2.6} />}
    </button>
  );
  const optCls = (o: PoolWord) => (fb ? (o.id === w.id ? " is-right" : picked === o.id ? " is-wrong" : " is-dim") : "");
  const instr = INSTR[step.kind];
  // Подсказка-картинка для заданий «напиши/собери»: фото, а если его нет — предложение с пропуском.
  const Cue = ({ size = 160 }: { size?: number }) => (
    hasImg(w.image_url) || !canGap(w)
      ? <WordArt src={w.image_url} word={w.text_en} code={code} topic={topic} size={size} className="t-photo-sm" hideWord />
      : <Sentence text={w.example_en ?? ""} word={w.text_en} gap={!fb} />
  );

  return (
    <div className="t-wrap" style={{ ["--c" as string]: tr.color || "#5B4BDB" }}>
      <header className="t-top">
        <a className="t-x" href="/words" aria-label={ru ? "Закончить" : "Quit"}><X size={26} strokeWidth={3} /></a>
        <div className="t-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <motion.i animate={{ width: `${Math.max(4, progress)}%` }} transition={{ type: "spring", stiffness: 120, damping: 20 }} />
        </div>
        {mode === "sprint" && <span className="t-timer"><Timer size={20} strokeWidth={2.6} />{left}</span>}
        <AnimatePresence>{combo >= 3 && (
          <motion.span key={combo} className="t-combo" initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ opacity: 0 }}>
            <Zap size={18} strokeWidth={2.6} fill="currentColor" />{combo}
          </motion.span>
        )}</AnimatePresence>
        <button className={"t-x t-hint-toggle" + (hints ? " is-on" : "")} onClick={toggleHints}
          aria-label={hints ? "Скрыть подсказки на русском" : "Показывать подсказки на русском"} title={hints ? "Подсказки на русском: вкл." : "Подсказки на русском: выкл."}>
          <Languages size={22} strokeWidth={2.4} />
        </button>
        <button className="t-x" onClick={() => { setMuted(!muted); setMute(!muted); }} aria-label={muted ? (ru ? "Включить звук" : "Sound on") : (ru ? "Выключить звук" : "Sound off")}>
          {muted ? <VolumeX size={24} strokeWidth={2.4} /> : <Volume2 size={24} strokeWidth={2.4} />}
        </button>
      </header>

      <AnimatePresence mode="wait">
        <motion.main className="t-stage" key={idx}
          initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}
          transition={{ type: "spring", stiffness: 260, damping: 26 }}>
          <div className="t-instr"><p>{instr[0]}</p>{hints && <span>{instr[1]}</span>}</div>

          {step.kind === "intro" && (
            <section className="t-intro">
              <div className="t-intro-card">
                <WordArt src={w.image_url} word={w.text_en} code={code} topic={topic} size={220} className="t-photo" />
                <div className="t-word-row"><h1 className="t-word">{w.text_en}</h1><Say /><Say slow /></div>
                {w.transcription && <p className="t-ipa">/{w.transcription}/</p>}
                {w.example_en && <div className="t-example"><Sentence text={w.example_en} word={w.text_en} /><Say text={w.example_en} /></div>}
                <Translation text={w.text_ru} />
              </div>
            </section>
          )}

          {step.kind === "flash" && <Flash w={w} ru={ru} code={code} topic={topic} token={token} disabled={!!fb}
            onAnswer={(ok) => void grade(ok, "flash")} />}

          {(step.kind === "listen_word" || step.kind === "gap") && (
            <section className="t-ask">
              <div className="t-prompt t-prompt-col">
                {step.kind === "listen_word" ? (
                  <div className="t-listen">
                    <button className="t-big-say" onClick={() => void speak(token, w.text_en)} aria-label={ru ? "Послушать ещё раз" : "Play again"}><Ear size={56} strokeWidth={2.2} /></button>
                    <Say slow />
                  </div>
                ) : (
                  <>
                    {hasImg(w.image_url) && <WordArt src={w.image_url} word={w.text_en} code={code} topic={topic} size={130} className="t-photo-sm" hideWord />}
                    <div className="t-example t-example-big"><Sentence text={w.example_en ?? ""} word={w.text_en} gap={!fb} /></div>
                  </>
                )}
              </div>
              <div className="t-options t-options-box">
                {step.options!.map((o, i) => (
                  <motion.button key={o.id} className={"t-opt" + optCls(o)} onClick={() => choose(o)} disabled={!!fb} whileTap={{ scale: 0.97 }}>
                    <span className="t-key">{i + 1}</span>{o.text_en}
                  </motion.button>
                ))}
              </div>
            </section>
          )}

          {(step.kind === "read_img" || step.kind === "listen_img") && (
            <section className="t-ask">
              <div className="t-word-row t-word-center">
                {step.kind === "read_img" && <h1 className="t-word">{w.text_en}</h1>}
                {step.kind === "listen_img"
                  ? <button className="t-big-say t-big-say-sm" onClick={() => void speak(token, w.text_en)} aria-label={ru ? "Послушать" : "Listen"}><Ear size={40} strokeWidth={2.2} /></button>
                  : <Say />}
              </div>
              <div className="t-imgs">
                {step.options!.map((o, i) => (
                  <motion.button key={o.id} className={"t-img" + optCls(o)} onClick={() => choose(o)} disabled={!!fb} aria-label={`${i + 1}`} whileTap={{ scale: 0.97 }}>
                    <img src={o.image_url} alt="" width={160} height={160} />
                    {fb && <span>{o.text_en}</span>}
                  </motion.button>
                ))}
              </div>
            </section>
          )}

          {step.kind === "tick" && step.sentence && (
            <section className="t-ask">
              <div className="t-tf">
                <WordArt src={w.image_url} word={w.text_en} code={code} topic={topic} size={210} className="t-photo" hideWord />
                <div className="t-tf-word t-tf-sentence"><p>{step.sentence}</p><Say text={step.sentence} /></div>
              </div>
              <div className="t-tf-btns">
                {[true, false].map((v) => (
                  <motion.button key={String(v)} whileTap={{ scale: 0.96 }} disabled={!!fb}
                    className={"t-tf-btn " + (v ? "is-yes" : "is-no") + (fb && picked === String(v) ? (fb.ok ? " is-right" : " is-wrong") : "")}
                    onClick={() => { setPicked(String(v)); void grade(step.truth === v, "tick"); }}
                    aria-label={v ? "Right" : "Wrong"}>
                    {v ? <Check size={30} strokeWidth={3.2} /> : <X size={30} strokeWidth={3.2} />}{v ? "Right" : "Wrong"}
                  </motion.button>
                ))}
              </div>
            </section>
          )}

          {step.kind === "missing" && step.masked && step.letterOpts && (
            <section className="t-ask">
              <div className="t-prompt t-prompt-col"><Cue size={150} />
                <div className="t-word-row"><h1 className="t-word t-masked">{[...step.masked].map((c, i) => <span key={i} className={c === "_" ? "t-gap" : ""}>{c === "_" ? (fb ? step.answerLetter : "") : c}</span>)}</h1><Say /></div></div>
              <div className="t-tiles">
                {step.letterOpts.map((l) => (
                  <motion.button key={l} whileTap={{ scale: 0.92 }} className={"t-tile" + (fb ? (l === step.answerLetter ? " is-right" : picked === l ? " is-wrong" : "") : "")} disabled={!!fb}
                    onClick={() => { setPicked(l); void grade(l === step.answerLetter, "missing"); }}>{l}</motion.button>
                ))}
              </div>
            </section>
          )}

          {step.kind === "spell" && step.letters && <Spell key={idx} word={w} letters={step.letters} cue={<Cue size={150} />}
            disabled={!!fb} onCheck={(ok) => void grade(ok, "spell")} token={token} />}

          {step.kind === "write" && <WriteIt key={idx} word={w} ru={ru} cue={<Cue size={150} />} disabled={!!fb}
            onCheck={(ok) => void grade(ok, "write")} token={token} />}

          {step.kind === "speak" && <SpeakIt key={idx} word={w} ru={ru} code={code} topic={topic} disabled={!!fb} token={token}
            onResult={(ok) => void grade(ok, "speak")} onSkip={next} />}

          {step.kind === "match" && step.pairs && <Match key={idx} words={step.pairs} token={token}
            onDone={() => { sfx("level"); celebrate(false); setFb({ ok: true }); }} />}
        </motion.main>
      </AnimatePresence>

      {mode !== "sprint" && (
        <footer className={"t-foot" + (fb ? (fb.ok ? " is-ok" : " is-bad") : "")}>
          <div className="t-foot-inner">
            <AnimatePresence>{fb ? (
              <motion.div className="t-fb" initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
                <span className="t-fb-icon">{fb.ok ? <Check size={30} strokeWidth={3.2} /> : <X size={28} strokeWidth={3.2} />}</span>
                <div>
                  <b>{fb.ok ? praise : (step.kind === "tick" ? (step.truth ? "It's right." : "It's wrong.") : "The answer is:")}</b>
                  {step.kind !== "match" && (
                    <p className="t-fb-word"><span>{w.text_en}</span>{w.example_en && <em>{w.example_en}</em>}</p>
                  )}
                  {step.kind !== "match" && <Translation text={w.text_ru} small />}
                </div>
              </motion.div>
            ) : <div />}</AnimatePresence>
            {(fb || step.kind === "intro") && (
              <button className={"k-btn k-btn-lg " + (fb && !fb.ok ? "k-btn-bad" : "k-btn-go")} onClick={next} autoFocus>
                {step.kind === "intro" ? "Got it" : "Continue"}
              </button>
            )}
          </div>
        </footer>
      )}
    </div>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return <div className="t-wrap"><div className="t-center">{children}</div></div>;
}

/** Предложение-пример: слово выделено или заменено пропуском. */
function Sentence({ text, word, gap = false }: { text: string; word: string; gap?: boolean }) {
  const loc = locate(text, word);
  if (!loc) return <p className="t-sentence">{text}</p>;
  return (
    <p className="t-sentence">
      {loc.a}{gap ? <span className="t-blank" aria-label="пропуск">{" ".repeat(Math.max(4, loc.m.length))}</span> : <mark>{loc.m}</mark>}{loc.b}
    </p>
  );
}

/** Перевод скрыт: ребёнок сначала понимает по картинке и контексту, а перевод открывает только если нужно. */
function Translation({ text, small = false }: { text: string; small?: boolean }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return open
    ? <p className={"t-ru" + (small ? " t-ru-sm" : "")}>{text}</p>
    : <button className={"t-ru-chip" + (small ? " t-ru-sm" : "")} onClick={() => setOpen(true)}><Languages size={16} strokeWidth={2.4} />Перевод</button>;
}

function Flash({ w, ru, code, topic, token, disabled, onAnswer }: {
  w: Word; ru: boolean; code: string; topic: string; token: string | null; disabled: boolean; onAnswer: (ok: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const front = hasImg(w.image_url) || !canGap(w);
  return (
    <section className="t-ask">
      <motion.button className="t-flash" onClick={() => { setOpen(true); void speak(token, w.text_en); }} animate={{ rotateY: open ? 180 : 0 }} transition={{ duration: 0.5 }}>
        <div className="t-flash-face">
          {front
            ? <WordArt src={w.image_url} word={w.text_en} code={code} topic={topic} size={190} hideWord />
            : <Sentence text={w.example_en ?? ""} word={w.text_en} gap />}
          <p className="t-flash-q">What is it?</p>
        </div>
        <div className="t-flash-face t-flash-back">
          <h1 className="t-word">{w.text_en}</h1>
          {w.transcription && <p className="t-ipa">/{w.transcription}/</p>}
          {w.example_en && <Sentence text={w.example_en} word={w.text_en} />}
        </div>
      </motion.button>
      <div className="t-tf-btns">
        {!open ? <button className="k-btn k-btn-light k-btn-lg" onClick={() => { setOpen(true); void speak(token, w.text_en); }}>{ru ? "Перевернуть" : "Turn the card"}</button> : (
          <>
            <button className="t-tf-btn is-no" disabled={disabled} onClick={() => onAnswer(false)}><X size={26} strokeWidth={3} />{ru ? "Не вспомнил" : "Didn't know"}</button>
            <button className="t-tf-btn is-yes" disabled={disabled} onClick={() => onAnswer(true)}><Check size={26} strokeWidth={3} />{ru ? "Знаю" : "I knew it"}</button>
          </>
        )}
      </div>
    </section>
  );
}

function Spell({ word, letters, cue, disabled, onCheck, token }: {
  word: Word; letters: string[]; cue: React.ReactNode; disabled: boolean; onCheck: (ok: boolean) => void; token: string | null;
}) {
  const [built, setBuilt] = useState<number[]>([]);
  const answer = built.map((i) => letters[i]).join("").replace(/␣/g, " ");
  useEffect(() => {
    if (built.length === letters.length && !disabled) onCheck(answer.toLowerCase() === word.text_en.toLowerCase());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [built.length]);
  return (
    <section className="t-ask">
      <div className="t-prompt t-prompt-col">{cue}
        <button className="t-say" onClick={() => void speak(token, word.text_en)} aria-label="Hint: listen"><Volume2 size={24} strokeWidth={2.6} /></button></div>
      <div className="t-slots" aria-live="polite">
        {letters.map((_, i) => (
          <button key={i} className={"t-slot" + (built[i] !== undefined ? " is-full" : "")} disabled={disabled || built[i] === undefined}
            onClick={() => setBuilt(built.filter((_, k) => k !== i))}>{built[i] !== undefined ? letters[built[i]].replace("␣", "·") : ""}</button>
        ))}
      </div>
      <div className="t-tiles">
        {letters.map((l, i) => (
          <motion.button key={i} whileTap={{ scale: 0.9 }} className={"t-tile" + (built.includes(i) ? " is-used" : "")} disabled={disabled || built.includes(i)}
            onClick={() => { sfx("tap"); setBuilt([...built, i]); }}>{l === "␣" ? "·" : l}</motion.button>
        ))}
      </div>
    </section>
  );
}

function WriteIt({ word, ru, cue, disabled, onCheck, token }: {
  word: Word; ru: boolean; cue: React.ReactNode; disabled: boolean; onCheck: (ok: boolean) => void; token: string | null;
}) {
  const [v, setV] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <section className="t-ask">
      <div className="t-prompt t-prompt-col">{cue}
        <button className="t-say" onClick={() => void speak(token, word.text_en)} aria-label="Hint: listen"><Volume2 size={24} strokeWidth={2.6} /></button></div>
      <form className="t-type" onSubmit={(e) => { e.preventDefault(); if (v.trim() && !disabled) onCheck(norm(v) === norm(word.text_en)); }}>
        <label className="sr-only" htmlFor="t-type-in">{ru ? "Ответ" : "Answer"}</label>
        <input id="t-type-in" ref={ref} value={v} onChange={(e) => setV(e.target.value)} disabled={disabled} autoComplete="off" autoCapitalize="none" spellCheck={false}
          placeholder={"_ ".repeat(word.text_en.length).trim()} />
        <button className="k-btn k-btn-go k-btn-lg" type="submit" disabled={disabled || !v.trim()}>Check</button>
      </form>
    </section>
  );
}

function SpeakIt({ word, ru, code, topic, disabled, token, onResult, onSkip }: {
  word: Word; ru: boolean; code: string; topic: string; disabled: boolean; token: string | null; onResult: (ok: boolean) => void; onSkip: () => void;
}) {
  const [state, setState] = useState<"idle" | "listening" | "heard">("idle");
  const [heard, setHeard] = useState("");
  const start = () => {
    const Rec = SR() as (new () => {
      lang: string; interimResults: boolean; maxAlternatives: number; start: () => void;
      onresult: (e: { results: { 0: { transcript: string }[] }[] & { [k: number]: ArrayLike<{ transcript: string }> } }) => void;
      onerror: () => void; onend: () => void;
    }) | undefined;
    if (!Rec) { onSkip(); return; }
    const r = new Rec();
    r.lang = "en-GB"; r.interimResults = false; r.maxAlternatives = 5;
    r.onresult = (e) => {
      const alts = Array.from(e.results[0] as ArrayLike<{ transcript: string }>).map((a) => norm(a.transcript));
      setHeard(alts[0] || "");
      setState("heard");
      onResult(alts.some((a) => a === norm(word.text_en) || a.split(" ").includes(norm(word.text_en))));
    };
    r.onerror = () => setState("idle");
    r.onend = () => setState((s) => (s === "listening" ? "idle" : s));
    setState("listening");
    r.start();
  };
  return (
    <section className="t-ask">
      <div className="t-prompt">
        <WordArt src={word.image_url} word={word.text_en} code={code} topic={topic} size={140} className="t-photo-sm" />
        <div><div className="t-word-row"><h1 className="t-word">{word.text_en}</h1>
          <button className="t-say" onClick={() => void speak(token, word.text_en)} aria-label={ru ? "Послушать" : "Listen"}><Volume2 size={24} strokeWidth={2.6} /></button></div>
          {word.transcription && <p className="t-ipa">/{word.transcription}/</p>}</div>
      </div>
      <div className="t-speak">
        <motion.button className={"t-mic" + (state === "listening" ? " is-on" : "")} onClick={start} disabled={disabled || state === "listening"}
          animate={state === "listening" ? { scale: [1, 1.08, 1] } : { scale: 1 }} transition={{ repeat: state === "listening" ? Infinity : 0, duration: 1 }}
          aria-label={ru ? "Нажми и скажи" : "Tap and speak"}><Mic size={44} strokeWidth={2.2} /></motion.button>
        <p>{state === "listening" ? "Listening…" : heard ? `I heard: "${heard}"` : (ru ? "Нажми на микрофон и скажи слово" : "Tap the mic and say the word")}</p>
        {!disabled && <button className="k-link-strong t-skip" onClick={onSkip}>{ru ? "Не могу сейчас говорить" : "Can't speak now"}</button>}
      </div>
    </section>
  );
}

/** Соедини слово и картинку (вместо пар «слово — перевод»). */
function Match({ words, token, onDone }: { words: Word[]; token: string | null; onDone: () => void }) {
  const left = useMemo(() => shuffle(words), [words]);
  const right = useMemo(() => shuffle(words), [words]);
  const [selL, setSelL] = useState<number | null>(null);
  const [selR, setSelR] = useState<number | null>(null);
  const [okIds, setOk] = useState<number[]>([]);
  const [bad, setBad] = useState<number[]>([]);
  useEffect(() => {
    if (selL === null || selR === null) return;
    if (selL === selR) {
      sfx("ok");
      const n = [...okIds, selL];
      setOk(n);
      if (n.length === words.length) setTimeout(onDone, 300);
    } else {
      sfx("bad");
      setBad([selL, selR]);
      setTimeout(() => setBad([]), 500);
    }
    setSelL(null);
    setSelR(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selL, selR]);
  return (
    <section className="t-ask">
      <div className="t-match t-match-img">
        <div>{left.map((w) => (
          <motion.button key={w.id} layout whileTap={{ scale: 0.96 }} className={"t-pair" + (okIds.includes(w.id) ? " is-right" : selL === w.id ? " is-sel" : bad.includes(w.id) ? " is-wrong" : "")}
            disabled={okIds.includes(w.id)} onClick={() => { setSelL(w.id); void speak(token, w.text_en); }}>{w.text_en}</motion.button>
        ))}</div>
        <div className="t-match-pics">{right.map((w) => (
          <motion.button key={w.id} layout whileTap={{ scale: 0.96 }} className={"t-pair t-pair-pic" + (okIds.includes(w.id) ? " is-right" : selR === w.id ? " is-sel" : bad.includes(w.id) ? " is-wrong" : "")}
            disabled={okIds.includes(w.id)} onClick={() => setSelR(w.id)} aria-label="picture"><img src={w.image_url} alt="" width={96} height={96} /></motion.button>
        ))}</div>
      </div>
    </section>
  );
}
