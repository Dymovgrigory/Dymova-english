"use client";

// Картинка слова: фото/иллюстрация, а если её нет — аккуратная цветная
// карточка с иконкой темы и первой буквой (без эмодзи).
import { topicLook } from "@/lib/topics";

// «Цвета» и «Числа» рисуем сами: настоящий цвет и крупная цифра
const COLORS: Record<string, [string, string]> = {
  red: ["#E53935", "#fff"], yellow: ["#FDD835", "#3a2a00"], green: ["#43A047", "#fff"], blue: ["#1E88E5", "#fff"],
  purple: ["#8E24AA", "#fff"], pink: ["#F48FB1", "#4a1030"], brown: ["#795548", "#fff"], black: ["#212121", "#fff"],
  white: ["#FFFFFF", "#333"], grey: ["#9E9E9E", "#fff"], gray: ["#9E9E9E", "#fff"], orange: ["#FB8C00", "#fff"],
  gold: ["linear-gradient(135deg,#f9e27a,#c9971c 55%,#f6d365)", "#4a3500"], silver: ["linear-gradient(135deg,#f2f2f2,#a9a9a9 55%,#e6e6e6)", "#333"],
  dark: ["#1b1530", "#fff"], light: ["#FFF8E1", "#7a5b00"],
  colourful: ["conic-gradient(#E53935,#FDD835,#43A047,#1E88E5,#8E24AA,#E53935)", "#fff"],
  colour: ["conic-gradient(#E53935,#FDD835,#43A047,#1E88E5,#8E24AA,#E53935)", "#fff"],
};
const NUMS: Record<string, string> = {
  zero: "0", one: "1", two: "2", three: "3", four: "4", five: "5", six: "6", seven: "7", eight: "8", nine: "9", ten: "10",
  eleven: "11", twelve: "12", thirteen: "13", fourteen: "14", fifteen: "15", sixteen: "16", seventeen: "17", eighteen: "18",
  nineteen: "19", twenty: "20", thirty: "30", forty: "40", fifty: "50", sixty: "60", seventy: "70", eighty: "80", ninety: "90",
  hundred: "100", thousand: "1000", million: "1 000 000", first: "1st", second: "2nd", third: "3rd", half: "½", double: "×2",
};

export default function WordArt({ src, word, code = "", topic = "", size = 160, className = "", hideWord = false }: {
  src?: string; word: string; code?: string; topic?: string; size?: number; className?: string;
  /** в заданиях «напиши/собери» слово на плитке не показываем — это была бы подсказка */
  hideWord?: boolean;
}) {
  const look = topicLook(code, topic);
  if (src && !src.startsWith("/wimg/")) {
    return <img className={"w-art " + className} src={src} alt="" width={size} height={size} style={{ width: size, height: size }} />;
  }
  const Icon = look.Icon;
  const key = word.toLowerCase();
  const isColours = code.includes("colours") || topic === "colours";
  const isNums = code.includes("numbers") || topic === "numbers";
  // цвет/число рисуем и в других наборах («Первые слова»), если фото нет
  const col = isColours || ["red","yellow","green","blue","purple","pink","brown","black","white","grey","gray","orange","colourful"].includes(key) ? COLORS[key] : undefined;
  if (col) {
    return (
      <span className={"w-art w-art-type w-art-swatch " + className} style={{ width: size, height: size, background: col[0], color: col[1] }} aria-hidden="true">
        {size >= 100 && !hideWord && <b style={{ fontSize: Math.round(Math.min(size * 0.22, (size * 0.86) / (key.length * 0.56))) }}>{word}</b>}
      </span>
    );
  }
  const num = isNums || !["first", "second", "third", "half", "double"].includes(key) ? NUMS[key] : undefined;
  if (num) {
    return (
      <span className={"w-art w-art-type " + className} style={{ width: size, height: size, ["--c" as string]: look.color }} aria-hidden="true">
        <b style={{ fontSize: Math.round(Math.min(size * 0.5, (size * 0.86) / (num.length * 0.62))) }}>{num}</b>
      </span>
    );
  }
  if (size < 100 || hideWord) {
    // в маленьких плитках слово уже написано рядом — показываем только иконку темы
    return (
      <span className={"w-art w-art-type " + className} style={{ width: size, height: size, ["--c" as string]: look.color, ["--ci" as string]: look.ink }} aria-hidden="true">
        <Icon size={Math.round(size * (hideWord ? 0.4 : 0.46))} strokeWidth={2} className="w-art-icon" />
      </span>
    );
  }
  // размер шрифта подбираем так, чтобы самое длинное слово строки не разрывалось
  const longest = Math.max(...word.split(/\s+/).map((x) => x.length), 1);
  const fs = Math.round(Math.min(size * 0.24, (size * 0.86) / (longest * 0.56)));
  return (
    <span className={"w-art w-art-type " + className} style={{ width: size, height: size, ["--c" as string]: look.color, ["--ci" as string]: look.ink }} aria-hidden="true">
      <Icon size={Math.round(size * 0.22)} strokeWidth={2.2} className="w-art-icon" />
      <b style={{ fontSize: fs }}>{word}</b>
    </span>
  );
}
