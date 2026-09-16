"use client";

import { SpeakButton } from "@/ui/SpeakButton";
import { EchoMic } from "@/ui/EchoMic";

type Props = {
  en?: string;
  ru?: string;
  ipa?: string;
  image?: string;
  speak?: string;
  exampleEn?: string;
  exampleRu?: string;
  teachRu?: string;
  onEchoPass?: () => void;
  onEchoBlocked?: (reason: string) => void;
};

const FRAME = "relative grid h-[min(46vh,340px)] w-full place-items-center bg-[#f4ecd8]";

const NUM: Record<string, string> = {
  one: "1",
  two: "2",
  three: "3",
  four: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  nine: "9",
  ten: "10",
};

const GLYPH: Record<string, string> = {
  cake: "🎂",
  egg: "🥚",
  rubber: "🧼",
  ruler: "📏",
  case: "✏️",
  cow: "🐮",
  bee: "🐝",
  farm: "🚜",
  food: "🍞",
  foot: "🦶",
  fork: "🍴",
  jar: "🫙",
  king: "👑",
  leg: "🦵",
  lip: "👄",
  loaf: "🍞",
  man: "👨",
  map: "🗺️",
  oil: "🫒",
  pin: "📌",
  rain: "🌧️",
  ring: "💍",
  soap: "🧼",
  spoon: "🥄",
  stairs: "🪜",
  star: "⭐",
  tail: "🐕",
  vest: "🦺",
  web: "🕸️",
  yak: "🦬",
  zip: "👖",
  zoo: "🦁",
  coat: "🧥",
  ear: "👂",
  bat: "🦇",
  fan: "🪭",
  arm: "💪",
  boot: "👢",
  pan: "🍳",
  pot: "🍲",
  mum: "👩",
  dad: "👨",
  sister: "👧",
  brother: "👦",
  baby: "👶",
  family: "👨‍👩‍👧",
  friend: "🤝",
  play: "🎲",
  game: "🎯",
  school: "🏫",
  jump: "🤸",
  run: "🏃",
  sit: "🪑",
  stop: "🛑",
  toy: "🧸",
  happy: "😊",
  sad: "😢",
  smile: "😊",
  cry: "😭",
  pet: "🐾",
  hello: "👋",
  hi: "👋",
};

const WASH: Record<string, string> = {
  red: "#e24b4b",
  blue: "#3b6be0",
  green: "#3c9b58",
  yellow: "#f0c93a",
  black: "#241a30",
  white: "#f7f1e4",
};

function same(a?: string, b?: string) {
  const core = (s?: string) => (s || "").toLowerCase().replace(/[^a-zа-яё]+/gi, "");
  return core(a) === core(b);
}

export function WordCard({ en, ipa, image, speak, exampleEn, teachRu, onEchoPass, onEchoBlocked }: Props) {
  const photo = image && /\.(jpe?g|webp|png)$/i.test(image) ? `${image}?v=7` : "";
  const key = (en || "").toLowerCase();
  const mark = !photo ? NUM[key] || GLYPH[key] : "";
  const wash = WASH[key];
  const phrase = exampleEn && !same(exampleEn, en) ? exampleEn : "";
  return (
    <article className="mt-2 overflow-hidden rounded-[28px] bg-white shadow-[0_10px_0_rgba(58,41,83,0.08)]">
      {photo ? (
        <div className={FRAME} style={wash ? { background: wash } : undefined}>
          <img src={photo} alt={en || ""} className="absolute inset-0 h-full w-full object-contain object-center" />
        </div>
      ) : mark ? (
        <div className={FRAME} style={wash ? { background: wash } : { background: "#f4ecd8" }}>
          <span className="font-[family-name:var(--font-display)] text-[7rem] leading-none">{mark}</span>
        </div>
      ) : wash ? (
        <div className={FRAME} style={{ background: wash }}>
          <span className="rounded-full bg-white/80 px-4 py-2 text-sm font-extrabold text-[#241a30]">It is {en}</span>
        </div>
      ) : null}
      <div className="grid justify-items-center gap-2 px-5 py-6 text-center">
        <p className="font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none text-[#3a2953]">
          {en}
        </p>
        {ipa ? (
          <p className="rounded-full bg-[#3a2953] px-4 py-1 text-base font-bold text-[#f5ed75]">[{ipa}]</p>
        ) : null}
        {teachRu ? (
          <p className="max-w-[18rem] text-sm font-semibold leading-snug text-[#3a2953]/80">{teachRu}</p>
        ) : null}
        <SpeakButton text={speak || en} label="Слушать слово" tone="yellow" />
        <div className="mt-1">
          <EchoMic key={speak || en} target={speak || en} onPass={onEchoPass} onBlocked={onEchoBlocked} />
        </div>
        {phrase ? (
          <div className="mt-2 w-full rounded-2xl bg-[#f4ecd8] px-4 py-3">
            <p className="font-extrabold text-[#3a2953]">{phrase}</p>
            <div className="mt-3">
              <SpeakButton text={phrase} label="Слушать фразу" tone="orange" />
            </div>
          </div>
        ) : null}
      </div>
    </article>
  );
}
