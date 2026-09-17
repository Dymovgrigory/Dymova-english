"use client";

import { motion, useReducedMotion } from "motion/react";
import { useState, type Ref } from "react";

import { Icon, type IconName } from "@/design/Icon";
import { NODE_LABELS } from "@/lib/v2/pathLayout";
import type { LearningPath, NodeKind, PathModule, PathNode } from "@/lib/v2/types";

/* Башня учебника в стиле «живой миниатюры»: башня-герой, этажи-диорамы, окна-уроки. */

const KIND_ICON: Record<NodeKind, IconName> = {
  words: "star",
  phonics: "letters",
  grammar: "rule",
  chest: "chest",
  review: "repeat",
  module_test: "crown",
};

type PressNode = (node: PathNode) => void;

const floorImage = (moduleId: string) => `/content/modules/${moduleId.replace(".", "-")}.webp`;

function windowSprite(node: PathNode): string {
  if (node.kind === "chest") return "/content/ui/window-chest.webp";
  if (node.status === "locked") return "/content/ui/window-shutters.webp";
  if (node.status === "open") return "/content/ui/window-dark.webp";
  return "/content/ui/window-lit.webp";
}

function Medallion({ icon, tone }: { icon: IconName; tone: "brass" | "done" | "muted" }) {
  const look =
    tone === "done"
      ? "bg-[radial-gradient(circle_at_35%_30%,#b9f5e8,#3fae98_70%)] text-[#0d3b33]"
      : tone === "muted"
        ? "bg-[radial-gradient(circle_at_35%_30%,#8a8096,#4a4156_75%)] text-[#d9d2e3]"
        : "bg-[radial-gradient(circle_at_35%_30%,#fff2b8,#e3a93a_65%,#9a6414)] text-[#3a2208]";
  return (
    <span
      className={`absolute -bottom-2 left-1/2 flex size-8 -translate-x-1/2 items-center justify-center rounded-full ring-2 ring-[#2a1c10]/60 shadow-[0_3px_6px_rgb(0_0_0/0.5),inset_0_1px_0_rgb(255_255_255/0.6)] ${look}`}
    >
      <Icon name={icon} size={16} filled={icon === "star" || icon === "crown"} />
    </span>
  );
}

function WindowSlot({ node, onPress, currentRef }: { node: PathNode; onPress: PressNode; currentRef?: Ref<HTMLDivElement> }) {
  const reduce = useReducedMotion();
  const label = NODE_LABELS[node.kind];
  const { status } = node;
  const current = status === "current";
  return (
    <div ref={currentRef} className="relative flex flex-col items-center">
      {current && (
        // eslint-disable-next-line @next/next/no-img-element -- прозрачный Foxy над окном текущего урока
        <motion.img
          src="/content/foxy/wave.webp"
          alt=""
          className="pointer-events-none absolute -top-10 left-1/2 z-10 h-12 w-12 -translate-x-1/2 object-contain drop-shadow-[0_4px_6px_rgb(0_0_0/0.6)]"
          animate={reduce ? undefined : { y: [0, -4, 0] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <button
        type="button"
        onClick={() => onPress(node)}
        aria-label={`${label}${status === "locked" ? ", закрыто" : status === "completed" ? ", пройдено" : current ? ", начать" : ""}`}
        className="press group relative block h-[118px] w-[92px] rounded-t-full focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- спрайт окна из конвейера миниатюр */}
        <img
          src={windowSprite(node)}
          alt=""
          draggable={false}
          className={[
            "h-full w-full object-contain transition duration-200 group-hover:-translate-y-0.5",
            current ? "window-current" : "",
            status === "completed" ? "drop-shadow-[0_0_14px_rgb(255_190_90/0.6)]" : "drop-shadow-[0_8px_8px_rgb(0_0_0/0.55)]",
            status === "locked" ? "brightness-[0.8] saturate-[0.8]" : "",
          ].join(" ")}
        />
        <Medallion
          icon={status === "completed" ? "check" : status === "locked" ? "lock" : KIND_ICON[node.kind]}
          tone={status === "completed" ? "done" : status === "locked" ? "muted" : "brass"}
        />
      </button>
      <span className={`mt-4 rounded-full bg-black/55 px-2.5 py-0.5 text-center text-[12px] font-extrabold leading-4 ring-1 ring-white/10 ${status === "locked" ? "text-[#c9bfd8]/75" : "text-[#fff6e3]"}`}>
        {label}
      </span>
    </div>
  );
}

function Balcony({ node, onPress, currentRef }: { node: PathNode; onPress: PressNode; currentRef?: Ref<HTMLDivElement> }) {
  const locked = node.status === "locked";
  const done = node.status === "completed";
  return (
    <div ref={currentRef} className="mt-6">
      <button
        type="button"
        onClick={() => onPress(node)}
        aria-label={`Контрольная этажа${locked ? ", закрыто" : done ? `, пройдено, звёзд ${node.stars}` : ""}`}
        className={[
          "press relative flex w-full items-center gap-3 rounded-2xl py-2 pl-2 pr-4 text-left",
          "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]",
          locked ? "bg-[#120c1a]/80 text-[#d9d2e3] ring-1 ring-[#ffd36e]/25" : "mat-brass",
          node.status === "current" ? "window-current" : "",
        ].join(" ")}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- спрайт балкона */}
        <img src="/content/ui/window-balcony.webp" alt="" className={`h-20 w-20 object-contain ${locked ? "opacity-75 grayscale-[30%]" : ""}`} />
        <span className="flex-1">
          <span className="block font-fairy text-[18px] font-extrabold leading-6">Контрольная этажа</span>
          <span className="block text-[13px] font-bold opacity-80">
            {locked ? "Откроется после всех окон этажа" : done ? "Знамя поднято" : "Подними знамя этажа"}
          </span>
        </span>
        {done ? (
          <span className="flex gap-0.5" aria-hidden>
            {[1, 2, 3].map((n) => (
              <Icon key={n} name="star" size={18} filled={n <= node.stars} className={n <= node.stars ? "text-[#7a3d06]" : "text-[#7a3d06]/25"} />
            ))}
          </span>
        ) : (
          <Icon name={locked ? "lock" : "crown"} size={22} />
        )}
      </button>
    </div>
  );
}

function Floor({ module, onPress, currentRef }: { module: PathModule; onPress: PressNode; currentRef: Ref<HTMLDivElement> }) {
  const [imageBroken, setImageBroken] = useState(false);
  const windows = module.nodes.filter((n) => n.kind !== "module_test");
  const test = module.nodes.find((n) => n.kind === "module_test");
  const done = module.nodes.filter((n) => n.status === "completed").length;
  const complete = done === module.nodes.length;
  const firstCurrent = module.nodes.find((n) => n.status === "current")?.id;

  return (
    <section aria-labelledby={`${module.id}-title`} className="mat-stone relative rounded-[30px] p-2.5">
      <div className="relative aspect-[16/9] overflow-hidden rounded-[22px] bg-[#221833] shadow-[inset_0_0_0_1px_rgb(0_0_0/0.4)]">
        {!imageBroken && (
          // eslint-disable-next-line @next/next/no-img-element -- диорама этажа из конвейера
          <img src={floorImage(module.id)} alt="" className="h-full w-full object-cover" loading="lazy" onError={() => setImageBroken(true)} />
        )}
        <div className="absolute inset-0 shadow-[inset_0_0_40px_rgb(0_0_0/0.55)]" />
        <div className="absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-[#120c1a]/95 via-[#120c1a]/55 to-transparent" />
        <div className="absolute inset-x-4 bottom-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-[12px] font-extrabold tracking-wide text-[#ffd36e]">{module.label ?? `Модуль ${module.order}`}</p>
            <h2 id={`${module.id}-title`} className="font-fairy text-[27px] font-black leading-8 text-[#fff6e3] drop-shadow-[0_2px_4px_rgb(0_0_0/0.8)]">
              {module.title_en}
            </h2>
            <p className="text-[14px] font-semibold text-[#f6efe2]/85">{module.title_ru}</p>
          </div>
          <span className={`shrink-0 rounded-full px-3 py-1 text-[12px] font-extrabold ${complete ? "mat-brass" : "bg-black/45 text-[#f6efe2] ring-1 ring-white/15"}`}>
            {complete ? "Этаж пройден" : `${done} из ${module.nodes.length}`}
          </span>
        </div>
      </div>

      <div className="px-2 pb-4 pt-12">
        <div className="grid grid-cols-3 justify-items-center gap-x-2 gap-y-10">
          {windows.map((node) => (
            <WindowSlot key={node.id} node={node} onPress={onPress} currentRef={node.id === firstCurrent ? currentRef : undefined} />
          ))}
        </div>
        {test && <Balcony node={test} onPress={onPress} currentRef={test.id === firstCurrent ? currentRef : undefined} />}
      </div>
    </section>
  );
}

function Stairs({ progress }: { progress: number }) {
  const steps = 4;
  return (
    <div className="flex flex-col items-center gap-1 py-3" aria-hidden>
      {Array.from({ length: steps }, (_, i) => {
        const lit = steps - i <= Math.round(progress * steps);
        return (
          <span
            key={i}
            className={`h-3 rounded-[4px] ${lit ? "mat-brass" : "mat-stone"}`}
            style={{ width: 54 + i * 10, marginLeft: i % 2 ? 22 : -22 }}
          />
        );
      })}
    </div>
  );
}

function Hero({ bookId, title, grade, raised }: { bookId: string; title: string; grade: number; raised: boolean }) {
  const [broken, setBroken] = useState(false);
  return (
    <div className="relative -mx-4 mb-2 h-[62vh] min-h-[420px] overflow-hidden sm:mx-0 sm:rounded-[30px]">
      {!broken && (
        // eslint-disable-next-line @next/next/no-img-element -- башня-герой учебника
        <img src={`/content/towers/${bookId}.webp`} alt="" className="h-full w-full object-cover object-top" onError={() => setBroken(true)} />
      )}
      <div className="absolute inset-0 bg-gradient-to-b from-[#150f1f]/10 via-transparent to-[#150f1f]" />
      <div className="absolute inset-x-0 bottom-6 flex justify-center px-6">
        <div className="mat-brass rounded-2xl px-6 py-3 text-center">
          <p className="font-fairy text-[26px] font-black leading-7">{title}</p>
          <p className="text-[13px] font-extrabold opacity-80">{raised ? "Башня покорена!" : `${grade} класс · поднимайся к знамени`}</p>
        </div>
      </div>
    </div>
  );
}

export function Tower({ path, onPress, currentRef }: { path: LearningPath; onPress: PressNode; currentRef: Ref<HTMLDivElement> }) {
  const floors = [...path.modules].reverse();
  const tests = path.modules.flatMap((m) => m.nodes.filter((n) => n.kind === "module_test"));
  const raised = tests.length > 0 && tests.every((n) => n.status === "completed");

  return (
    <div className="flex flex-col items-stretch">
      <Hero bookId={path.book.id} title={path.book.title} grade={path.book.grade} raised={raised} />
      {floors.map((module, index) => {
        const below = floors[index + 1];
        const progress = below ? below.nodes.filter((n) => n.status === "completed").length / below.nodes.length : 0;
        return (
          <div key={module.id} className="flex flex-col items-stretch">
            <Floor module={module} onPress={onPress} currentRef={currentRef} />
            {below && <Stairs progress={progress} />}
          </div>
        );
      })}
      <p className="mt-6 text-center text-[13px] font-extrabold text-[#c9bfd8]/70">Вход в башню · начало учебника</p>
    </div>
  );
}
