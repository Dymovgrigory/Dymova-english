"use client";

// «Мой словарь»: все слова ребёнка — выученные, в процессе и трудные (с ошибками).
import { useEffect, useMemo, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import WordArt from "@/components/word-art";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, MyWord } from "@/lib/api";
import { speak } from "@/lib/sound";
import { Target, Volume2 } from "lucide-react";

export default function MyWordsPage() {
  return (
    <CabinetPage>
      <MyWords />
    </CabinetPage>
  );
}

type Tab = "all" | "learned" | "learning" | "hard";

function MyWords() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active } = useCabinet();
  const [data, setData] = useState<{ words: MyWord[]; hard_ids: number[]; learned: number; learning: number } | null>(null);
  const [tab, setTab] = useState<Tab>("all");
  const [q, setQ] = useState("");

  useEffect(() => {
    if (!token || !active) return;
    api.myWords(token, studentId).then(setData).catch(() => setData({ words: [], hard_ids: [], learned: 0, learning: 0 }));
  }, [token, active, studentId]);

  const hard = useMemo(() => new Set(data?.hard_ids ?? []), [data]);
  const list = (data?.words ?? []).filter((w) => {
    if (tab === "learned" && w.strength < 2) return false;
    if (tab === "learning" && w.strength >= 2) return false;
    if (tab === "hard" && !hard.has(w.id)) return false;
    const s = q.trim().toLowerCase();
    return !s || w.text_en.toLowerCase().includes(s) || w.text_ru.toLowerCase().includes(s);
  });

  const TABS: [Tab, string, number][] = [
    ["all", ru ? "Все" : "All", data?.words.length ?? 0],
    ["learned", ru ? "Выучено" : "Learned", data?.learned ?? 0],
    ["learning", ru ? "Учу" : "Learning", data?.learning ?? 0],
    ["hard", ru ? "Трудные" : "Tricky", data?.hard_ids.length ?? 0],
  ];

  return (
    <div className="k-dict">
      <section className="k-dict-head">
        <div>
          <h1>{ru ? "Мой словарь" : "My words"}</h1>
          <p>{data ? (ru ? `Слов в словаре: ${data.words.length}. Выучено: ${data.learned}.` : `${data.words.length} words, ${data.learned} learned.`) : "…"}</p>
        </div>
        {(data?.hard_ids.length ?? 0) > 0 && (
          <a className="k-btn k-btn-go k-btn-lg" href="/words/train/0"><Target size={20} strokeWidth={2.6} />{ru ? "Тренировать трудные" : "Practise tricky words"}</a>
        )}
      </section>
      <div className="k-tabs" role="tablist">
        {TABS.map(([k, t, n]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={"k-tab-btn" + (tab === k ? " is-on" : "")} onClick={() => setTab(k)}>
            {t} · {n}
          </button>
        ))}
      </div>
      <label className="k-search k-search-wide">
        <span className="sr-only">{ru ? "Найти слово" : "Find a word"}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ru ? "Найти слово" : "Find a word"} />
      </label>
      {data && data.words.length === 0 && (
        <div className="k-empty">
          <p>{ru ? "Здесь появятся слова, которые ты начнёшь учить." : "Words you start learning will appear here."}</p>
          <a className="k-btn k-btn-go" href="/words">{ru ? "Выбрать тему" : "Pick a topic"}</a>
        </div>
      )}
      <div className="k-dict-grid">
        {list.map((w) => (
          <button key={w.id} className="k-dict-card" onClick={() => void speak(token, w.text_en)}>
            <WordArt src={w.image_url} word={w.text_en} size={76} />
            <span className="k-dict-text">
              <b>{w.text_en}</b>
              {w.transcription && <span className="k-ipa">/{w.transcription}/</span>}
              {w.example_en && <span className="k-dict-ex">{w.example_en}</span>}
              <span className="k-dict-ru">{w.text_ru}</span>
            </span>
            <span className="k-dict-side">
              <Volume2 size={22} strokeWidth={2.6} />
              {hard.has(w.id) && <span className="k-tag-hard">{ru ? "трудное" : "tricky"}</span>}
              <span className="k-dots" aria-label={ru ? `Знание: ${w.strength} из 5` : `Strength ${w.strength} of 5`}>
                {[0, 1, 2, 3, 4].map((i) => <i key={i} className={w.strength > i ? "on" : ""} />)}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
