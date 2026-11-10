"use client";

import { useEffect, useMemo, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, CollectionCard } from "@/lib/api";

export default function CollectionPage() {
  return <CabinetPage><Collection /></CabinetPage>;
}

function Collection() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token, studentId, active } = useCabinet();
  const [cards, setCards] = useState<CollectionCard[]>([]);
  const [unlocked, setUnlocked] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !active) return;
    api.learningCollection(token, studentId).then((result) => {
      setCards(result.cards);
      setUnlocked(result.unlocked);
    }).catch(() => setError(ru ? "Не удалось загрузить коллекцию." : "Could not load the collection."));
  }, [token, studentId, active, ru]);

  const groups = useMemo(() => Array.from(new Map(cards.map((card) => [card.collection_id, card.collection_title_ru])).entries()), [cards]);
  return <div className="k-page-grid">
    <div className="k-words-head"><div><h1>{ru ? "Коллекция героев" : "Hero collection"}</h1><p>{ru ? `${unlocked} из ${cards.length || 100} карточек открыто через обучение` : `${unlocked} of ${cards.length || 100} cards unlocked through learning`}</p></div></div>
    {error && <div className="k-alert">{error}</div>}
    {groups.map(([id, title]) => <section className="k-panel" key={id}><div className="k-panel-head"><h2>{title}</h2><span>{cards.filter((card) => card.collection_id === id && card.unlocked).length}/10</span></div><div className="k-collection-grid">{cards.filter((card) => card.collection_id === id).map((card) => <article className={`k-collection-card${card.unlocked ? " is-unlocked" : ""}`} key={card.id}><div className="k-collection-art">{card.unlocked ? <img src={card.asset} alt="" /> : <span>?</span>}</div><b>{ru ? card.title_ru : card.title_en}</b><small>{card.unlocked ? (ru ? "Открыта" : "Unlocked") : (ru ? `Нужно: ${card.unlock_value}` : `Need: ${card.unlock_value}`)}</small></article>)}</div></section>)}
  </div>;
}
