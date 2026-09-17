"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/design/Button";
import { Foxy } from "@/design/Foxy";
import { Seal } from "@/design/Seal";
import { Shell } from "@/design/Shell";
import { StatPill } from "@/design/StatPill";
import { isProfileMissing, isUnauthorized, v2 } from "@/lib/v2/client";
import { NODE_LABELS, nodeOffset } from "@/lib/v2/pathLayout";
import type { Courses, Home, LearningPath, PathNode } from "@/lib/v2/types";

type Loaded = { home: Home; courses: Courses; path: LearningPath };

const AMPLITUDE = 72;

async function loadAll(bookId?: string): Promise<Loaded | "onboarding" | { error: string }> {
  try {
    const [home, courses] = await Promise.all([v2.home(), v2.courses()]);
    const path = await v2.path(bookId ?? home.profile.book_id);
    return { home, courses, path };
  } catch (err) {
    if (isProfileMissing(err) || isUnauthorized(err)) return "onboarding";
    return { error: err instanceof Error ? err.message : "Не получилось загрузить путь." };
  }
}

export function PathScreen() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const [data, setData] = useState<Loaded | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [hint, setHint] = useState<{ nodeId: string; text: string } | null>(null);
  const [bookMenu, setBookMenu] = useState(false);
  const currentRef = useRef<HTMLDivElement | null>(null);

  const apply = useCallback(
    (result: Awaited<ReturnType<typeof loadAll>>) => {
      if (result === "onboarding") router.replace("/onboarding");
      else if ("error" in result) setProblem(result.error);
      else {
        setProblem(null);
        setData(result);
      }
    },
    [router],
  );

  useEffect(() => {
    let alive = true;
    loadAll().then((result) => alive && apply(result));
    return () => {
      alive = false;
    };
  }, [apply]);

  useEffect(() => {
    currentRef.current?.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
  }, [data?.path.book.id, reduce]);

  const press = async (node: PathNode) => {
    if (node.status === "locked") {
      setHint({ nodeId: node.id, text: "Сначала пройди уроки выше" });
      return;
    }
    if (node.kind === "chest") {
      if (node.status === "completed") {
        setHint({ nodeId: node.id, text: "Сундук уже открыт" });
        return;
      }
      try {
        const opened = await v2.openChest(node.id);
        setHint({ nodeId: node.id, text: `+${opened.coins} монет для замка!` });
        apply(await loadAll(data?.path.book.id));
      } catch (err) {
        setHint({ nodeId: node.id, text: err instanceof Error ? err.message : "Не открылся" });
      }
      return;
    }
    router.push(`/lesson/${node.id}`);
  };

  const home = data?.home;
  const top = (
    <header className="sticky top-0 z-20 border-b-2 border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 px-4 py-3">
        <div className="relative">
          <button
            type="button"
            onClick={() => setBookMenu((open) => !open)}
            aria-expanded={bookMenu}
            className="flex items-center gap-2 rounded-xl border-2 border-line bg-white px-3 py-2 text-[16px] font-extrabold text-royal focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30"
          >
            {data ? data.path.book.title : "Spotlight"}
            <span aria-hidden className="text-ink-soft">▾</span>
          </button>
          {bookMenu && data && (
            <ul className="absolute left-0 top-12 z-30 w-60 overflow-hidden rounded-2xl border-2 border-line bg-white shadow-lg">
              {data.courses.books.map((book) => (
                <li key={book.id}>
                  <button
                    type="button"
                    onClick={async () => {
                      setBookMenu(false);
                      apply(await loadAll(book.id));
                    }}
                    className={`flex w-full items-center justify-between px-4 py-3 text-left text-[16px] font-bold hover:bg-grid/60 ${
                      book.id === data.path.book.id ? "text-royal" : "text-ink"
                    }`}
                  >
                    <span>{book.title}</span>
                    <span className="text-[13px] text-ink-soft">{book.grade} класс</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {home && (
          <div className="flex items-center gap-4">
            <StatPill icon="flame" value={home.streak_days} label="Дней подряд" dim={home.streak_days === 0} />
            <StatPill icon="bolt" value={`${home.today_xp}/${home.daily_goal_xp}`} label="Опыт сегодня из цели" dim={!home.goal_reached} />
            <StatPill icon="coin" value={home.player.coins} label="Монеты" />
          </div>
        )}
      </div>
    </header>
  );

  return (
    <Shell top={top}>
      <div className="mx-auto max-w-2xl px-4 pb-16 pt-6">
        {problem && (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <Foxy pose="think" size={140} />
            <p className="text-[18px] font-extrabold text-ink">{problem}</p>
            <Button onClick={async () => apply(await loadAll())}>Обновить</Button>
          </div>
        )}
        {!data && !problem && <p className="py-20 text-center text-[18px] font-extrabold text-ink-soft" role="status">Открываем учебник…</p>}

        {data && home && home.due_count > 0 && (
          <button
            type="button"
            onClick={() => router.push("/lesson/practice")}
            className="press mb-8 flex w-full items-center justify-between gap-3 rounded-3xl border-2 border-mint-edge/50 bg-mint-wash px-5 py-4 text-left shadow-[0_4px_0_var(--color-mint-edge)]"
          >
            <span>
              <span className="block text-[18px] font-extrabold text-mint-ink">Пора повторить: {home.due_count}</span>
              <span className="block text-[15px] font-semibold text-mint-ink/80">Слова начинают забываться — 3 минуты, и они снова твои</span>
            </span>
            <span className="text-[16px] font-extrabold text-mint-ink">Повторить</span>
          </button>
        )}

        {data && !data.path.modules.length && (
          <p className="rounded-3xl border-2 border-line bg-white p-6 text-center text-[18px] font-bold text-ink-soft">
            Уроки для {data.path.book.title} скоро появятся.
          </p>
        )}

        {data?.path.modules.map((module) => {
          return (
            <section key={module.id} className="mb-14" aria-labelledby={`${module.id}-title`}>
              <div className="sticky top-[70px] z-10 mb-10 rounded-3xl bg-royal px-5 py-4 text-white shadow-[0_6px_0_var(--color-royal-edge)]">
                <p className="text-[14px] font-bold text-crown">Модуль {module.order}</p>
                <h2 id={`${module.id}-title`} className="font-heading text-[26px] font-extrabold leading-8">{module.title_en}</h2>
                <p className="text-[16px] font-semibold text-white/75">{module.title_ru}</p>
              </div>

              <ol className="flex flex-col items-center gap-7">
                {module.nodes.map((node, position) => {
                  const offset = nodeOffset(position, AMPLITUDE);
                  const current = node.status === "current";
                  return (
                    <li key={node.id} className="relative flex flex-col items-center" style={{ transform: `translateX(${offset}px)` }}>
                      <div ref={current ? currentRef : undefined} className="relative flex flex-col items-center">
                        {current && (
                          <motion.span
                            initial={reduce ? false : { y: 6, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            className="mb-2 rounded-xl border-2 border-line bg-white px-3 py-1 text-[15px] font-extrabold text-royal shadow-[0_3px_0_var(--color-line)]"
                          >
                            Начать
                          </motion.span>
                        )}
                        <Seal kind={node.kind} status={node.status} stars={node.stars} label={NODE_LABELS[node.kind]} onPress={() => void press(node)} />
                        <span className={`mt-2 text-[14px] font-extrabold ${node.status === "locked" ? "text-ink-soft/60" : "text-ink-soft"}`}>
                          {NODE_LABELS[node.kind]}
                        </span>
                        {current && (
                          <Foxy
                            pose="wave"
                            size={96}
                            className={`pointer-events-none absolute top-4 ${offset > 0 ? "-left-28" : "-right-28"}`}
                          />
                        )}
                        <AnimatePresence>
                          {hint?.nodeId === node.id && (
                            <motion.button
                              type="button"
                              onClick={() => setHint(null)}
                              initial={{ opacity: 0, y: -4 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              className="absolute top-full z-10 mt-8 whitespace-nowrap rounded-xl bg-royal-deep px-3 py-2 text-[14px] font-bold text-white"
                              role="status"
                            >
                              {hint.text}
                            </motion.button>
                          )}
                        </AnimatePresence>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          );
        })}
      </div>
    </Shell>
  );
}
