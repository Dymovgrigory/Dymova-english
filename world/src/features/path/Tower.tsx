"use client";

import { motion, useReducedMotion } from "motion/react";
import { useState, type Ref } from "react";

import { Icon, type IconName } from "@/design/Icon";
import { NODE_LABELS } from "@/lib/v2/pathLayout";
import type { LearningPath, NodeKind, PathModule, PathNode } from "@/lib/v2/types";

/* Башня учебника: крыша со знаменем сверху, этажи-модули, ворота внизу. */

const KIND_ICON: Record<NodeKind, IconName> = {
  words: "star",
  phonics: "letters",
  grammar: "rule",
  chest: "chest",
  review: "repeat",
  module_test: "crown",
};

const STONE =
  "bg-[#b8a6dc] [background-image:repeating-linear-gradient(0deg,transparent_0_26px,rgb(58_41_83/0.10)_26px_28px),repeating-linear-gradient(90deg,transparent_0_52px,rgb(58_41_83/0.07)_52px_54px)]";

type PressNode = (node: PathNode) => void;

function moduleImage(moduleId: string): string {
  return `/content/modules/${moduleId.replace(".", "-")}.webp`;
}

function WindowSlot({ node, onPress, currentRef }: { node: PathNode; onPress: PressNode; currentRef?: Ref<HTMLDivElement> }) {
  const reduce = useReducedMotion();
  const label = NODE_LABELS[node.kind];
  const { status } = node;
  const glass =
    status === "completed"
      ? "bg-[radial-gradient(circle_at_50%_35%,#fff7c2,#f5d64a_60%,#d8a92c)] text-royal-deep shadow-[0_0_22px_rgb(245_214_74/0.65)]"
      : status === "current"
        ? "bg-[radial-gradient(circle_at_50%_30%,#fffbe0,#f5ed75_55%,#e8b93e)] text-royal-deep shadow-[0_0_0_4px_#fff,0_0_30px_rgb(245_237_117/0.9)]"
        : status === "open"
          ? "bg-[linear-gradient(160deg,#4a3a6b,#2a1f3d)] text-mint"
          : "bg-[#6b4a2e]";

  return (
    <div ref={currentRef} className="relative flex flex-col items-center gap-1.5">
      {status === "current" && (
        // eslint-disable-next-line @next/next/no-img-element -- маленький прозрачный Foxy над окном
        <motion.img
          src="/content/foxy/wave.webp"
          alt=""
          className="pointer-events-none absolute -top-11 left-1/2 z-10 h-12 w-12 -translate-x-1/2 object-contain drop-shadow"
          animate={reduce ? undefined : { y: [0, -4, 0] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      {node.kind === "chest" ? (
        <button
          type="button"
          onClick={() => onPress(node)}
          aria-label={`Сундук${status === "locked" ? ", закрыто" : status === "completed" ? ", открыт" : ", открыть"}`}
          className={[
            "press flex h-[84px] w-[64px] items-end justify-center rounded-2xl border-[5px] border-[#5b4580] pb-2",
            "bg-[linear-gradient(180deg,#2a1f3d,#4a3a6b)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-crown",
            status === "current" || status === "open" ? "seal-current" : "",
          ].join(" ")}
        >
          <Icon
            name="chest"
            size={36}
            filled={status === "completed"}
            className={status === "locked" ? "text-[#8f7bb8]" : status === "completed" ? "text-crown/60" : "text-crown"}
          />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onPress(node)}
          aria-label={`${label}${status === "locked" ? ", закрыто" : status === "completed" ? ", пройдено" : status === "current" ? ", начать" : ""}`}
          className={[
            "press relative flex h-[84px] w-[64px] items-center justify-center overflow-hidden rounded-t-full rounded-b-lg",
            "border-[5px] border-[#5b4580] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-crown",
            glass,
            status === "current" ? "seal-current" : "",
          ].join(" ")}
        >
          {status === "locked" ? (
            <>
              <span className="absolute inset-y-0 left-0 w-1/2 border-r-2 border-[#4b321e] bg-[repeating-linear-gradient(90deg,#7a5536_0_7px,#6b4a2e_7px_9px)]" />
              <span className="absolute inset-y-0 right-0 w-1/2 bg-[repeating-linear-gradient(90deg,#7a5536_0_7px,#6b4a2e_7px_9px)]" />
              <Icon name="lock" size={20} className="relative text-[#f3d9a8]" />
            </>
          ) : (
            <>
              <span className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 bg-[#5b4580]/35" aria-hidden />
              <span className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-[#5b4580]/35" aria-hidden />
              <Icon name={status === "completed" ? "check" : KIND_ICON[node.kind]} size={24} filled={status !== "completed" && node.kind === "words"} className="relative" />
            </>
          )}
        </button>
      )}
      <span className={`text-center text-[12px] font-extrabold leading-4 ${status === "locked" ? "text-royal-deep/55" : "text-royal-deep"}`}>
        {label}
      </span>
    </div>
  );
}

function Balcony({ node, onPress, currentRef }: { node: PathNode; onPress: PressNode; currentRef?: Ref<HTMLDivElement> }) {
  const locked = node.status === "locked";
  const done = node.status === "completed";
  return (
    <div ref={currentRef} className="mt-4 flex justify-center">
      <button
        type="button"
        onClick={() => onPress(node)}
        aria-label={`Контрольная модуля${locked ? ", закрыто" : done ? `, пройдено, звёзд ${node.stars}` : ""}`}
        className={[
          "press flex w-full max-w-[320px] items-center gap-3 rounded-2xl border-4 px-4 py-2.5 text-left",
          "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-crown",
          done
            ? "border-crown-edge bg-crown text-royal-deep shadow-[0_5px_0_var(--color-crown-edge)]"
            : node.status === "current"
              ? "seal-current border-crown-edge bg-[#fff6b8] text-royal-deep shadow-[0_5px_0_var(--color-crown-edge)]"
              : locked
                ? "border-[#5b4580] bg-[#8d78b5] text-white/70 shadow-[0_5px_0_#5b4580]"
                : "border-[#5b4580] bg-royal text-white shadow-[0_5px_0_var(--color-royal-edge)]",
        ].join(" ")}
      >
        <svg width="34" height="40" viewBox="0 0 34 40" aria-hidden className="shrink-0">
          <path d="M4 2v38" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          <path d={done ? "M5 4h24l-6 7 6 7H5z" : "M5 20h24l-6 7 6 7H5z"} fill={done ? "#3a2953" : "#ff6b5e"} />
        </svg>
        <span className="flex-1">
          <span className="block text-[16px] font-extrabold">Контрольная модуля</span>
          <span className="block text-[13px] font-bold opacity-80">
            {locked ? "Откроется после уроков этажа" : done ? "Флаг поднят" : "Подними флаг этажа"}
          </span>
        </span>
        {done ? (
          <span className="flex gap-0.5" aria-hidden>
            {[1, 2, 3].map((n) => (
              <Icon key={n} name="star" size={18} filled={n <= node.stars} className={n <= node.stars ? "text-royal" : "text-royal/25"} />
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
    <section aria-labelledby={`${module.id}-title`} className={`relative overflow-hidden rounded-[28px] border-[6px] border-[#8f7bb8] shadow-[0_10px_0_#6f5a99] ${STONE}`}>
      <div className="relative aspect-[16/8] w-full overflow-hidden bg-royal">
        {!imageBroken && (
          // eslint-disable-next-line @next/next/no-img-element -- иллюстрация этажа, webp из конвейера
          <img
            src={moduleImage(module.id)}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
            onError={() => setImageBroken(true)}
          />
        )}
        <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-royal-deep/85 to-transparent" />
        <div className="absolute inset-x-4 bottom-3 flex items-end justify-between gap-3 text-white">
          <div>
            <p className="text-[13px] font-extrabold text-crown">{module.label ?? `Модуль ${module.order}`}</p>
            <h2 id={`${module.id}-title`} className="font-heading text-[24px] font-extrabold leading-7 drop-shadow">
              {module.title_en}
            </h2>
            <p className="text-[14px] font-semibold text-white/85">{module.title_ru}</p>
          </div>
          <span
            className={`shrink-0 rounded-full px-3 py-1 text-[13px] font-extrabold ${complete ? "bg-crown text-royal-deep" : "bg-white/20 text-white"}`}
          >
            {complete ? "Этаж пройден" : `${done}/${module.nodes.length}`}
          </span>
        </div>
      </div>

      <div className="px-3 pb-5 pt-12">
        <div className="grid grid-cols-4 justify-items-center gap-x-2 gap-y-9">
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
  const steps = 5;
  return (
    <div className="flex flex-col-reverse items-center gap-[3px] py-2" aria-hidden>
      {Array.from({ length: steps }, (_, i) => (
        <span
          key={i}
          className={`h-[7px] rounded-sm ${i < Math.round(progress * steps) ? "bg-crown shadow-[0_2px_0_var(--color-crown-edge)]" : "bg-[#8f7bb8] shadow-[0_2px_0_#6f5a99]"}`}
          style={{ width: 70 - i * 6, marginLeft: i % 2 ? 18 : -18 }}
        />
      ))}
    </div>
  );
}

function Roof({ title, grade, raised }: { title: string; grade: number; raised: boolean }) {
  const reduce = useReducedMotion();
  return (
    <div className="relative mx-auto flex w-full max-w-[420px] flex-col items-center">
      <svg viewBox="0 0 300 150" className="w-[78%]" aria-hidden>
        <path d="M150 34 L270 146 H30 Z" fill="#3a2953" />
        <path d="M150 34 L270 146 H150 Z" fill="#2c1f41" />
        <path d="M150 34 V4" stroke="#241a30" strokeWidth="4" strokeLinecap="round" />
        <motion.path
          d="M152 6 h46 l-12 11 12 11 h-46 z"
          fill={raised ? "#f5ed75" : "#b8a6dc"}
          initial={false}
          animate={reduce ? undefined : { skewY: [0, 3, 0] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
        <circle cx="150" cy="96" r="18" fill="#f5ed75" stroke="#d8b72c" strokeWidth="4" />
      </svg>
      <div className="-mt-2 rounded-2xl bg-royal px-5 py-2 text-center text-white shadow-[0_5px_0_var(--color-royal-edge)]">
        <p className="font-heading text-[20px] font-extrabold leading-6">{title}</p>
        <p className="text-[13px] font-bold text-crown">{raised ? "Башня покорена!" : `${grade} класс · поднимайся на вершину`}</p>
      </div>
    </div>
  );
}

function Gates() {
  return (
    <div className="flex flex-col items-center pt-2">
      <div className={`flex h-24 w-40 items-end justify-center rounded-t-full border-[6px] border-[#8f7bb8] ${STONE}`}>
        <div className="h-16 w-16 rounded-t-full border-4 border-[#4b321e] bg-[repeating-linear-gradient(90deg,#7a5536_0_8px,#6b4a2e_8px_10px)]" />
      </div>
      <div className="h-3 w-64 rounded-full bg-[#8f7bb8]/60" />
      <p className="mt-2 text-[13px] font-extrabold text-ink-soft">Вход в башню</p>
    </div>
  );
}

export function Tower({ path, onPress, currentRef }: { path: LearningPath; onPress: PressNode; currentRef: Ref<HTMLDivElement> }) {
  const floors = [...path.modules].reverse();
  const tests = path.modules.flatMap((m) => m.nodes.filter((n) => n.kind === "module_test"));
  const raised = tests.length > 0 && tests.every((n) => n.status === "completed");

  return (
    <div className="flex flex-col items-stretch">
      <Roof title={path.book.title} grade={path.book.grade} raised={raised} />
      {floors.map((module, index) => {
        const below = floors[index + 1];
        const progress = below ? below.nodes.filter((n) => n.status === "completed").length / below.nodes.length : 0;
        return (
          <div key={module.id} className="flex flex-col items-stretch">
            {index === 0 && <div className="h-3" />}
            <Floor module={module} onPress={onPress} currentRef={currentRef} />
            {below && <Stairs progress={progress} />}
          </div>
        );
      })}
      <Gates />
    </div>
  );
}
