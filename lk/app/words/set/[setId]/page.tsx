"use client";

import { use, useEffect, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, SetWord, WordSet } from "@/lib/api";
import { speak } from "@/lib/sound";
import { Ear, GalleryVerticalEnd, PencilLine, Sparkles, Timer, Volume2 } from "lucide-react";
import WordArt from "@/components/word-art";
import { topicLook } from "@/lib/topics";

export default function SetPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = use(params);
  return (
    <CabinetPage>
      <SetWords setId={Number(setId)} />
    </CabinetPage>
  );
}

function SetWords({ setId }: { setId: number }) {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active } = useCabinet();
  const [words, setWords] = useState<SetWord[] | null>(null);
  const [info, setInfo] = useState<WordSet | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!token || !active) return;
    api.setWords(token, studentId, setId).then((r) => setWords(r.words)).catch(() => setWords([]));
    api.wordSets(token, studentId).then((r) => setInfo(r.sets.find((s) => s.id === setId) ?? null)).catch(() => {});
  }, [token, active, studentId, setId]);

  const list = (words ?? []).filter((w) =>
    !q.trim() || w.text_en.toLowerCase().includes(q.toLowerCase()) || w.text_ru.toLowerCase().includes(q.toLowerCase()));

  const look = topicLook(info?.code ?? "", info?.topic);
  const MODES = [
    { m: "classic", Icon: Sparkles, t: ru ? "Тренировка" : "Practice", d: ru ? "Урок: знакомство, задания, повторение" : "Meet, practise, review" },
    { m: "listen", Icon: Ear, t: ru ? "На слух" : "Listening", d: ru ? "Listen and choose" : "Listen and choose" },
    { m: "spell", Icon: PencilLine, t: ru ? "Правописание" : "Spelling", d: ru ? "Look and spell, look and write" : "Look and spell, look and write" },
    { m: "sprint", Icon: Timer, t: ru ? "Спринт 60 секунд" : "60-second sprint", d: ru ? "Сколько успеешь?" : "How many can you do?" },
    { m: "cards", Icon: GalleryVerticalEnd, t: ru ? "Карточки" : "Flashcards", d: ru ? "Вспомни и переверни" : "Recall and flip" },
  ];
  return (
    <div className="k-dict" style={{ ["--c" as string]: look.color }}>
      <a className="k-back" href="/words">{ru ? "← Все словари" : "← All word lists"}</a>
      <section className="k-dict-head">
        <div>
          <h1>{info?.title ?? "…"}</h1>
          <p>{words ? (ru ? `${words.length} слов · нажми на слово, чтобы послушать` : `${words.length} words · tap a word to hear it`) : "…"}</p>
        </div>
        <a className="k-btn k-btn-go k-btn-lg" href={`/words/train/${setId}`}>{ru ? "Тренировать" : "Practise"}</a>
      </section>
      <div className="k-modes">
        {MODES.map(({ m, Icon, t, d }) => (
          <a key={m} className="k-mode" href={`/words/train/${setId}${m === "classic" ? "" : `?mode=${m}`}`}>
            <span className="k-mode-ic"><Icon size={26} strokeWidth={2.4} /></span>
            <b>{t}</b><span>{d}</span>
          </a>
        ))}
      </div>
      <label className="k-search k-search-wide">
        <span className="sr-only">{ru ? "Найти слово" : "Find a word"}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ru ? "Найти слово" : "Find a word"} />
      </label>
      <div className="k-dict-grid">
        {list.map((w) => (
          <button key={w.id} className="k-dict-card" onClick={() => void speak(token, w.text_en)}>
            <WordArt src={w.image_url} word={w.text_en} code={info?.code ?? ""} topic={info?.topic ?? ""} size={76} />
            <span className="k-dict-text">
              <b>{w.text_en}</b>
              {w.transcription && <span className="k-ipa">/{w.transcription}/</span>}
              {w.example_en && <span className="k-dict-ex">{w.example_en}</span>}
              <span className="k-dict-ru">{w.text_ru}</span>
            </span>
            <span className="k-dict-side">
              <Volume2 size={22} strokeWidth={2.6} />
              <span className="k-dots" aria-label={ru ? `Знание: ${w.strength ?? 0} из 5` : `Strength ${w.strength ?? 0} of 5`}>
                {[0, 1, 2, 3, 4].map((i) => <i key={i} className={(w.strength ?? -1) > i ? "on" : ""} />)}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
