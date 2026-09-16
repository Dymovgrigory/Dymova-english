"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  worldApi,
  type LessonAnswerResult,
  type LessonFinish,
  type LessonSession,
} from "@/lib/api";
import { Hearts, Stars } from "@/ui/Marks";
import { TheoryArt } from "@/ui/TheoryArt";
import { FoxiGuide } from "@/ui/FoxiGuide";
import { WordCard } from "@/ui/WordCard";
import { PhraseCard } from "@/ui/PhraseCard";
import { SpeakButton } from "@/ui/SpeakButton";
import { EchoMic } from "@/ui/EchoMic";
import { ChromeIcon } from "@/ui/fantasy/Chrome";
import { speakEnglish, playClip } from "@/lib/speak";
import { needsEchoFor } from "@/lib/echo";
import { playCorrect, playHeart, playWrong } from "@/lib/sfx";
import { Burst, SkyWash } from "@/ui/Fx";
import { foxiSrc } from "@/lib/foxiPoses";
import { loadJourney, recordLessonFinish } from "@/lib/journey";

const STAGE_RU: Record<string, string> = {
  warmup: "Приветствие",
  theory: "Правило",
  words: "Слова",
  listen: "Слушаем",
  practice: "Тренировка",
  wrap: "Итог",
};

const LETTER_ART = new Set(["letters-st", "letters-ae", "vowels", "consonants"]);

export default function LessonPage() {
  const params = useParams<{ lessonId: string }>();
  const router = useRouter();
  const lessonId = decodeURIComponent(params.lessonId);
  const [session, setSession] = useState<LessonSession | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Record<number, LessonAnswerResult>>({});
  const [typed, setTyped] = useState("");
  const [choice, setChoice] = useState<number | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});
  const [picked, setPicked] = useState<string | null>(null);
  const [built, setBuilt] = useState<string[]>([]);
  const [finish, setFinish] = useState<LessonFinish | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [echoOk, setEchoOk] = useState(false);
  const [shownAt, setShownAt] = useState(() => Date.now());
  const homeHref = lessonId === "practice" ? "/world" : "/learn";

  useEffect(() => {
    let name = "Исследователь";
    try {
      name = window.localStorage.getItem("world.name") || name;
    } catch {
      /* private mode */
    }
    const begin = () => (lessonId === "practice" ? worldApi.startPractice() : worldApi.startLesson(lessonId));
    void worldApi
      .ensurePlayer(name)
      .then(() => begin())
      .catch(async (err) => {
        const msg = err instanceof Error ? err.message : "";
        if (msg.includes("409") || msg.includes("no hearts") || msg.includes("hearts")) {
          throw new Error("Нет сердец. Купи пополнение в Лавке Фокси (350 монет).");
        }
        throw err;
      })
      .then((s) => {
        setError(null);
        setSession(s);
        if (s.items[0]?.kind === "listen" && s.items[0].speak) void speakEnglish(s.items[0].speak);
        if (s.items[0]?.speak_sound) playClip(s.items[0].audio, s.items[0].speak_sound);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Урок не открылся. Запусти make world-dev."));
  }, [lessonId]);

  const item = session?.items[index];
  const result = item ? results[item.index] : undefined;
  const hearts = result?.hearts ?? session?.hearts ?? 5;
  const progress = session ? ((index + (result ? 1 : 0)) / session.total) * 100 : 0;

  useEffect(() => {
    setShownAt(Date.now());
  }, [index, item?.index]);

  const needsEcho = needsEchoFor(item?.kind);

  const canCheck = useMemo(() => {
    if (!item || result) return false;
    if (needsEcho && !echoOk) return false;
    if (item.kind === "explain" || item.kind === "word_card" || item.kind === "phrase_card") return true;
    if (item.kind === "type_en") return typed.trim().length > 0;
    if (item.kind === "match") return Object.keys(matches).length === (item.left?.length ?? 0);
    if (item.kind === "tap_build") return built.length === (item.bank?.length ?? 0) && built.length > 0;
    if (item.kind === "fill_blank" || item.kind === "mcq_en_ru" || item.kind === "mcq_ru_en" || item.kind === "listen") {
      return choice !== null;
    }
    return choice !== null;
  }, [item, result, typed, matches, choice, built, echoOk, needsEcho]);

  const payload = (): Record<string, unknown> => {
    if (!item) return {};
    const latency_ms = Math.max(0, Date.now() - shownAt);
    if (item.kind === "explain" || item.kind === "word_card" || item.kind === "phrase_card") {
      return { latency_ms };
    }
    if (item.kind === "type_en") return { text: typed, latency_ms };
    if (item.kind === "match") return { matches, latency_ms };
    if (item.kind === "tap_build") return { tokens: built, latency_ms };
    return { choice, latency_ms };
  };

  const goNext = (from: number, failed?: boolean) => {
    if (!session) return "stay";
    if (failed) {
      router.push(homeHref);
      return "map";
    }
    if (from < session.items.length - 1) {
      const nxt = session.items[from + 1];
      setIndex(from + 1);
      setTyped("");
      setChoice(null);
      setMatches({});
      setPicked(null);
      setBuilt([]);
      setEchoOk(false);
      const autoSpeak =
        nxt.kind === "listen" ||
        nxt.kind === "word_card" ||
        nxt.kind === "phrase_card" ||
        nxt.kind === "type_en" ||
        nxt.kind === "tap_build";
      if (autoSpeak && nxt.speak) void speakEnglish(nxt.speak);
      if (nxt.speak_sound) playClip(nxt.audio, nxt.speak_sound);
      return "next";
    }
    return "finish";
  };

  const check = async () => {
    if (!session || !item || result || busy || !canCheck) return;
    setBusy(true);
    try {
      const res = await worldApi.answerLesson(session.session_id, item.index, payload());
      if (res.correct) playCorrect();
      else {
        playWrong();
        if (res.hearts < hearts) playHeart();
      }
      setResults((r) => ({ ...r, [item.index]: res }));
      if ((item.kind === "explain" || item.kind === "word_card" || item.kind === "phrase_card") && !res.failed) {
        goNext(index, false);
      }
    } catch {
      setError("Ответ не ушёл.");
    } finally {
      setBusy(false);
    }
  };

  const cont = async () => {
    if (!session || !item) return;
    const step = goNext(index, result?.failed);
    if (step !== "finish") return;
    setBusy(true);
    try {
      const done = await worldApi.finishLesson(session.session_id);
      recordLessonFinish({
        practice: Boolean(done.practice),
        itemsGranted: (done.items_granted?.length ?? 0) > 0,
        dueAfter: 0,
        level: done.player?.level,
        streakDays: done.player?.streak_days,
      });
      setFinish(done);
    } catch {
      setError("Не вышло закрыть урок.");
    } finally {
      setBusy(false);
    }
  };

  const prompt = useMemo(() => {
    if (!item) return "";
    if (item.kind === "explain") return item.title_ru || "Урок";
    if (item.kind === "word_card") return item.en || "Новое слово";
    if (item.kind === "match") return "Соедини пары";
    if (item.kind === "type_en") return "Напиши по-английски";
    if (item.kind === "fill_blank") return "Выбери слово";
    if (item.kind === "tap_build") return "Собери фразу";
    return item.prompt ?? "";
  }, [item]);

  if (finish) {
    const pulse = loadJourney().lastRewardBuilding || "lexicon";
    return (
      <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-[#241a30] p-6 text-white">
        <div
          aria-hidden
          className="absolute inset-0 bg-cover bg-center opacity-70"
          style={{ backgroundImage: "url(/world/cinematic/gates-foxi.png)" }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#241a30] via-[#241a30]/75 to-[#241a30]/35" />
        <div aria-hidden className="world-embers absolute inset-0" />
        <Burst show />
        <div className="world-reward-pop relative z-10 w-full max-w-md text-center">
          <Stars count={finish.stars} onDark />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={foxiSrc("cheer")}
            alt="Foxy"
            className="mx-auto mt-4 h-48 w-auto object-contain object-bottom drop-shadow-xl"
          />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/world/ui/rewards/chest-open.png"
            alt=""
            className="mx-auto mt-2 h-20 w-auto object-contain drop-shadow-lg"
            aria-hidden
          />
          <h1 className="mt-4 font-[family-name:var(--font-display)] text-4xl font-extrabold">
            {finish.practice ? "Двор закрыт" : "Урок закрыт"}
          </h1>
          <p className="mt-3 text-lg font-semibold text-white/90">
            {finish.score} из {finish.total} · +{finish.xp_delta} XP · +{finish.coins_delta} FoxCoins
          </p>
          <div className="mx-auto mt-4 h-3 w-56 overflow-hidden rounded-full bg-white/15" aria-hidden>
            <div
              className="h-full rounded-full bg-[#7fd8c9] transition-[width] duration-500"
              style={{ width: `${Math.min(100, Math.round((finish.score / Math.max(1, finish.total)) * 100))}%` }}
            />
          </div>
          {finish.daily_xp != null ? (
            <p className="mt-3 text-sm font-bold text-[#f5ed75]/90">
              Сегодня {finish.daily_xp} из {finish.daily_goal ?? 50} XP
            </p>
          ) : null}
          {(finish.items_granted?.length ?? 0) > 0 ? (
            <p className="mt-2 text-sm font-bold text-[#f5ed75]">Новые стикеры в альбоме!</p>
          ) : null}
          <div className="mt-8 grid gap-3">
            <button
              onClick={() =>
                router.push(
                  finish.daily_xp != null && finish.daily_goal != null && finish.daily_xp >= finish.daily_goal
                    ? "/world?pulse=quests"
                    : `/world?pulse=${pulse}`,
                )
              }
              className="w-full border border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] py-4 font-[family-name:var(--font-display)] text-lg font-extrabold text-[#241a30] shadow-[0_5px_0_#9a7a18]"
              style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
            >
              {finish.daily_xp != null && finish.daily_goal != null && finish.daily_xp >= finish.daily_goal
                ? "Забрать награду дня"
                : "В замок за наградой"}
            </button>
            <button
              onClick={() => router.push("/learn")}
              className="w-full border border-[#7fd8c9]/35 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] py-4 font-[family-name:var(--font-display)] text-lg font-extrabold text-[#f5ed75]"
              style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
            >
              На карту уроков
            </button>
          </div>
        </div>
      </main>
    );
  }

  const footerTone = result
    ? result.correct
      ? "bg-[#7fd8c9] text-[#13332c]"
      : "bg-[#ee7349] text-white"
    : "bg-white";
  const nextItem = session?.items[index + 1];

  let continueLabel = "Дальше";
  if (result?.failed) continueLabel = "На карту";
  else if (!nextItem) continueLabel = "Закрыть урок";
  else if (nextItem.kind === "explain") continueLabel = nextItem.stage === "wrap" ? "Итог" : "Дальше";
  else if (nextItem.kind === "listen") continueLabel = "Слушаем";
  else if (item?.kind === "listen") continueLabel = "К тренировке";

  let checkLabel = "Проверить";
  if (needsEcho && !echoOk) {
    checkLabel = "Сначала повтори вслух";
  } else if (item?.kind === "explain" || item?.kind === "word_card" || item?.kind === "phrase_card") {
    if (nextItem?.kind === "explain" || nextItem?.kind === "word_card" || nextItem?.kind === "phrase_card") {
      checkLabel = "Дальше";
    } else if (nextItem?.kind === "listen") {
      checkLabel = "Слушаем";
    } else {
      checkLabel = "К упражнениям";
    }
  }

  return (
    <main className="relative flex min-h-dvh flex-col overflow-hidden bg-[#f7f1e4] text-[#241a30]">
      <SkyWash image="/world/cinematic/gates-foxi.png" />
      <Burst show={Boolean(result?.correct)} />
      <header className="relative z-10 flex items-center gap-3 px-4 pt-4">
        <button
          type="button"
          onClick={() => router.push(homeHref)}
          className="relative grid h-10 w-10 place-items-center overflow-hidden border border-[#f5ed75]/45 bg-[#3a2953] shadow-[0_3px_0_rgba(36,26,48,0.25)]"
          style={{ clipPath: "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)" }}
          aria-label="Закрыть"
        >
          <ChromeIcon name="back" className="h-5 w-5" />
        </button>
        <div
          className="h-4 flex-1 overflow-hidden border border-[#3a2953]/20 bg-[#3a2953]/15"
          style={{ clipPath: "polygon(2% 0, 98% 0, 100% 50%, 98% 100%, 2% 100%, 0 50%)" }}
        >
          <div
            className="h-full bg-[linear-gradient(90deg,#f5ed75,#e8b93e)] transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <Hearts count={hearts} />
      </header>

      <div className="relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col px-5 pb-44 pt-3">
        {error ? <p className="mb-3 text-sm text-[#ee7349]">{error}</p> : null}
        {session && item ? (
          <>
            <FoxiGuide
              pose={item.foxi_pose || "wave"}
              size={item.kind === "word_card" || item.kind === "phrase_card" ? "sm" : "md"}
              kicker={item.kind === "word_card" || item.kind === "phrase_card" ? undefined : `${STAGE_RU[item.stage || ""] || (item.kind === "explain" ? "Теория" : "Упражнение")} · ${session.spot_ru || session.title_ru}`}
              line={
                item.kind === "word_card"
                  ? item.teach_ru || "Смотри. Скажи фразу, не перевод."
                  : item.kind === "phrase_card"
                    ? item.foxi_ru || "Слушай фразу целиком и повтори."
                    : item.foxi_ru || "Сначала смысл ситуации, потом звук, потом ты."
              }
            />
            {item.kind !== "word_card" && item.kind !== "phrase_card" ? (
              <>
                <p className="mt-1 text-sm font-semibold text-[#afafaf]">{session.title_ru}</p>
                <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl font-extrabold leading-tight text-[#3c3c3c]">
                  {prompt}
                </h1>
              </>
            ) : null}
            {item.kind === "explain" ? (
              <div className="mt-4 space-y-4">
                {item.gpc ? (
                  <button
                    type="button"
                    onClick={() => playClip(item.audio, item.speak_sound || item.speak)}
                    className="flex w-full items-center justify-between border-2 border-[#e5e5e5] bg-[#f7f1e4] px-5 py-4 text-left shadow-[0_4px_0_#e5e5e5]"
                    style={{ clipPath: "polygon(3% 0, 97% 0, 100% 10%, 100% 90%, 97% 100%, 3% 100%, 0 90%, 0 10%)" }}
                  >
                    <span>
                      <span className="block text-xs font-bold text-[#afafaf]">Нажми и повтори звук</span>
                      <span className="mt-1 block font-[family-name:var(--font-display)] text-5xl font-extrabold text-[#3a2953]">
                        {item.gpc}
                      </span>
                      <span className="text-[#ee7349]">{item.sound}</span>
                    </span>
                    <span
                      className="grid h-16 w-16 place-items-center border border-[#f5ed75]/40 bg-[#3a2953] text-2xl text-[#f5ed75]"
                      style={{ clipPath: "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)" }}
                    >
                      ▶
                    </span>
                  </button>
                ) : null}
                {item.image ? (
                  <img
                    src={item.image}
                    alt=""
                    className="mx-auto max-h-56 w-full rounded-[28px] object-contain"
                  />
                ) : item.visual_id && item.visual_id !== "foxi-hello" && !(LETTER_ART.has(item.visual_id) && !item.gpc) ? (
                  <TheoryArt id={item.visual_id} />
                ) : null}
                <p className="text-base leading-relaxed text-[#3c3c3c]">{item.body_ru}</p>
                {item.speak ? (
                  <SpeakButton text={item.speak} label={`Слушать ${item.example_en || "фразу"}`} tone="orange" />
                ) : null}
                {(item.steps || []).length > 0 ? (
                  <ol className="grid gap-2">
                    {item.steps?.map((step, i) => (
                      <li
                        key={`${i}-${step}`}
                        className="flex items-start gap-3 border-2 border-[#e5e5e5] bg-white px-4 py-3 text-sm font-semibold"
                        style={{ clipPath: "polygon(4% 0, 96% 0, 100% 14%, 100% 86%, 96% 100%, 4% 100%, 0 86%, 0 14%)" }}
                      >
                        <span
                          className="grid h-8 w-8 shrink-0 place-items-center bg-[#3a2953] text-[#f5ed75]"
                          style={{ clipPath: "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)" }}
                        >
                          {i + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ol>
                ) : null}
                {item.example_en ? (
                  <p className="rounded-2xl bg-[#f7f1e4] px-4 py-3 text-[#3c3c3c]">
                    <span className="font-bold">{item.example_en}</span>
                    {item.example_ru ? <span className="mt-1 block text-sm opacity-70">{item.example_ru}</span> : null}
                  </p>
                ) : null}
              </div>
            ) : null}
            {item.kind === "word_card" ? (
              <WordCard
                key={item.index}
                en={item.en}
                ru={item.ru}
                ipa={item.ipa}
                image={item.image}
                speak={item.speak}
                exampleEn={item.example_en}
                exampleRu={item.example_ru}
                teachRu={item.teach_ru}
                onEchoPass={() => setEchoOk(true)}
                onEchoBlocked={() => setEchoOk(true)}
              />
            ) : null}
            {item.kind === "phrase_card" ? (
              <PhraseCard
                key={item.index}
                en={item.en}
                ru={item.ru}
                speak={item.speak}
                onEchoPass={() => setEchoOk(true)}
                onEchoBlocked={() => setEchoOk(true)}
              />
            ) : null}
            {item.kind === "fill_blank" ? (
              <p className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold">{item.prompt}</p>
            ) : null}
            {item.kind === "fill_blank" && item.hint_ru ? (
              <p className="mt-1 text-[#afafaf]">{item.hint_ru}</p>
            ) : null}
            {item.kind === "tap_build" && item.prompt ? (
              <p className="mt-2 text-lg text-[#777]">{item.prompt}</p>
            ) : null}
            {item.ipa && item.kind !== "listen" && item.kind !== "word_card" ? <p className="mt-1 text-[#3a2953] font-semibold">{item.ipa}</p> : null}

            {item.kind === "listen" ? (
              <div className="mt-4 grid justify-items-start gap-2">
                <SpeakButton text={item.speak} label="Слушать" tone="blue" />
                <EchoMic
                  key={item.index}
                  target={item.speak}
                  onPass={() => setEchoOk(true)}
                  onBlocked={() => setEchoOk(true)}
                />
              </div>
            ) : null}
            {item.kind === "mcq_en_ru" && item.image ? (
              <img src={item.image} alt="" className="mx-auto mt-3 h-32 w-auto object-contain" />
            ) : null}
            {item.kind === "mcq_en_ru" && item.prompt ? (
              <SpeakButton text={item.speak || item.prompt} label="Слушать слово" tone="blue" />
            ) : null}
            {item.kind === "type_en" && item.speak ? (
              <SpeakButton text={item.speak} label="Слушать слово" tone="blue" />
            ) : null}
            {item.kind === "tap_build" && item.speak ? (
              <SpeakButton text={item.speak} label="Слушать фразу" tone="blue" />
            ) : null}
            {item.kind === "match" ? (
              <p className="mt-2 text-sm text-[#afafaf]">Слева слово, справа фраза. Сначала послушай ▶</p>
            ) : null}

            <div className="mt-8 flex flex-1 flex-col gap-3">
              {item.kind === "type_en" ? (
                <input
                  value={typed}
                  disabled={Boolean(result)}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder="cat"
                  className="border-2 border-[#241a30]/15 px-4 py-4 text-xl outline-none focus:border-[#3a2953]"
                  style={{ clipPath: "polygon(4% 0, 96% 0, 100% 16%, 100% 84%, 96% 100%, 4% 100%, 0 84%, 0 16%)" }}
                />
              ) : null}

              {(item.kind === "mcq_en_ru" ||
                item.kind === "mcq_ru_en" ||
                item.kind === "listen" ||
                item.kind === "fill_blank") &&
                item.options?.map((option, i) => {
                  const selected = choice === i;
                  const good = Boolean(result && i === result.correct_index);
                  const bad = Boolean(result && selected && !result.correct);
                  let tone = "border-[#241a30]/12 bg-white";
                  if (good) tone = "border-[#3a2953] bg-[#f5ed75]/40";
                  else if (bad) tone = "border-[#ee7349] bg-[#ee7349]/10";
                  else if (selected) tone = "border-[#3a2953] bg-[#f5ed75]/30";
                  return (
                    <button
                      key={`${option}-${i}`}
                      disabled={Boolean(result)}
                      onClick={() => setChoice(i)}
                      className={`border-2 px-4 py-4 text-left text-lg font-semibold ${tone}`}
                      style={{ clipPath: "polygon(4% 0, 96% 0, 100% 16%, 100% 84%, 96% 100%, 4% 100%, 0 84%, 0 16%)" }}
                    >
                      {option}
                    </button>
                  );
                })}

              {item.kind === "match" ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-2">
                    {item.left?.map((en) => (
                      <button
                        key={en}
                        disabled={Boolean(result) || Boolean(matches[en])}
                        onClick={() => {
                          setPicked(en);
                          void speakEnglish(en);
                        }}
                        className={`border-2 px-3 py-3 font-bold ${
                          picked === en ? "border-[#ee7349] bg-[#ee7349]/10" : "border-[#241a30]/12"
                        }`}
                        style={{ clipPath: "polygon(6% 0, 94% 0, 100% 18%, 100% 82%, 94% 100%, 6% 100%, 0 82%, 0 18%)" }}
                      >
                        {en}
                      </button>
                    ))}
                  </div>
                  <div className="grid gap-2">
                    {item.right?.map((ru) => {
                      const taken = Object.values(matches).includes(ru);
                      return (
                        <button
                          key={ru}
                          disabled={!picked || taken || Boolean(result)}
                          onClick={() => {
                            if (!picked) return;
                            setMatches((m) => ({ ...m, [picked]: ru }));
                            setPicked(null);
                          }}
                          className="border-2 border-[#241a30]/12 px-3 py-3 disabled:opacity-30"
                          style={{ clipPath: "polygon(6% 0, 94% 0, 100% 18%, 100% 82%, 94% 100%, 6% 100%, 0 82%, 0 18%)" }}
                        >
                          {ru}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {item.kind === "tap_build" ? (
                <div className="flex flex-col gap-4">
                  <div
                    className="flex min-h-16 flex-wrap gap-2 border-2 border-dashed border-[#241a30]/15 p-3"
                    style={{ clipPath: "polygon(4% 0, 96% 0, 100% 12%, 100% 88%, 96% 100%, 4% 100%, 0 88%, 0 12%)" }}
                  >
                    {built.length === 0 ? (
                      <span className="text-[#241a30]/30">Нажми слова внизу</span>
                    ) : (
                      built.map((token, i) => (
                        <button
                          key={`built-${i}-${token}`}
                          disabled={Boolean(result)}
                          onClick={() => setBuilt((row) => row.filter((_, j) => j !== i))}
                          className="border-2 border-[#3a2953] bg-[#f5ed75]/40 px-3 py-2 font-bold"
                          style={{ clipPath: "polygon(10% 0, 90% 0, 100% 50%, 90% 100%, 10% 100%, 0 50%)" }}
                        >
                          {token}
                        </button>
                      ))
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(item.bank ?? []).map((token, i) => {
                      const sameBefore = (item.bank ?? []).slice(0, i).filter((t) => t === token).length;
                      const used = built.filter((t) => t === token).length;
                      if (used > sameBefore) return null;
                      return (
                        <button
                          key={`bank-${i}-${token}`}
                          disabled={Boolean(result)}
                          onClick={() => setBuilt((row) => [...row, token])}
                          className="border-2 border-[#241a30]/12 bg-white px-3 py-2 font-bold"
                          style={{ clipPath: "polygon(10% 0, 90% 0, 100% 50%, 90% 100%, 10% 100%, 0 50%)" }}
                        >
                          {token}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          </>
        ) : (
          <p className="text-[#afafaf]">Готовим урок…</p>
        )}
      </div>

      <footer className={`fixed inset-x-0 bottom-0 z-30 border-t-2 border-[#e5e5e5] px-5 py-4 ${footerTone}`}>
        <div className="mx-auto flex max-w-lg items-center justify-between gap-4">
          {result ? (
            <>
              <div>
                <p className="font-[family-name:var(--font-display)] text-xl font-extrabold">
              {result.failed ? "Сердца кончились" : result.correct ? (item?.kind === "explain" ? "Понятно" : "Верно") : "Правильный ответ"}
                </p>
                {result.correct_text ? <p className="text-sm opacity-80">{result.correct_text}</p> : null}
                {result.tokens_correct ? <p className="text-sm opacity-80">{result.tokens_correct.join(" ")}</p> : null}
                {result.example_en ? <p className="text-sm opacity-80">{result.example_en}</p> : null}
              </div>
              <button
                onClick={() => void cont()}
                disabled={busy}
                className="shrink-0 border border-[#f5ed75]/55 bg-[linear-gradient(180deg,rgba(58,41,83,0.98),rgba(36,26,48,1))] px-6 py-3 font-[family-name:var(--font-display)] text-sm font-extrabold text-[#f5ed75] shadow-[0_4px_0_#1a1230]"
                style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
              >
                {continueLabel}
              </button>
            </>
          ) : (
            <button
              onClick={() => void check()}
              disabled={!canCheck || busy}
              className="w-full border border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] py-4 font-[family-name:var(--font-display)] text-lg font-extrabold text-[#241a30] shadow-[0_5px_0_#9a7a18] disabled:border-transparent disabled:bg-[#241a30]/15 disabled:text-[#241a30]/30 disabled:shadow-none"
              style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
            >
              {checkLabel}
            </button>
          )}
        </div>
      </footer>
    </main>
  );
}
