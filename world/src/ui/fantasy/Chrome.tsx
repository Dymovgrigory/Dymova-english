import type { ReactNode, ButtonHTMLAttributes, CSSProperties } from "react";
import Link from "next/link";

/** Shared fantasy chrome — castle metal frames, proportional plaques, atlas tiles. */

const metalBorder =
  "border-[1.5px] border-[#f5ed75]/55 shadow-[inset_0_1px_0_rgba(255,246,168,0.35),inset_0_-2px_0_rgba(0,0,0,0.35),0_0_0_1px_rgba(58,41,83,0.5),0_8px_24px_rgba(0,0,0,0.35)]";

const HEX_CLIP = "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)";
const CHIP_CLIP = "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)";
const PANEL_CLIP = "polygon(3% 0, 97% 0, 100% 8%, 100% 92%, 97% 100%, 3% 100%, 0 92%, 0 8%)";
const STAT_CLIP = "polygon(2% 0, 98% 0, 100% 18%, 100% 82%, 98% 100%, 2% 100%, 0 82%, 0 18%)";
const CLOSE_CLIP = "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)";

/** atlas-buttons.png = 4×6 hex plaques (Meshy batch). Pick one cell as the face. */
function buttonFace(col: number, row: number): CSSProperties {
  const x = (col / 3) * 100;
  const y = (row / 5) * 100;
  return {
    backgroundImage: "url(/world/ui/frames/atlas-buttons.png)",
    backgroundSize: "400% 600%",
    backgroundPosition: `${x}% ${y}%`,
    backgroundRepeat: "no-repeat",
  };
}

/** Single extracted plaque — avoids crooked full-atlas stretch on panels. */
const PANEL_FACE: CSSProperties = {
  backgroundImage: "url(/world/ui/frames/panel-plaque.png)",
  backgroundSize: "100% 100%",
  backgroundPosition: "center",
  backgroundRepeat: "no-repeat",
};

/** Soft metal wash from frames atlas (gem mid-nodes), not a stretched sheet. */
const PANEL_ORNAMENT: CSSProperties = {
  backgroundImage: "url(/world/ui/frames/atlas-frames.png)",
  backgroundSize: "220% auto",
  backgroundPosition: "12% 18%",
  backgroundRepeat: "no-repeat",
};

const PLAQUE_FACE: CSSProperties = {
  backgroundImage: "url(/world/ui/frames/quest-plaque.png)",
  backgroundSize: "contain",
  backgroundPosition: "center top",
  backgroundRepeat: "no-repeat",
};

export function FantasyPanel({
  children,
  className = "",
  wide = false,
}: {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}) {
  return (
    <div
      className={`relative mx-auto w-full ${wide ? "max-w-lg" : "max-w-[min(92vw,22rem)]"} ${className}`}
    >
      <div
        className={`relative overflow-hidden rounded-[18px] bg-[#241a30] px-4 py-3.5 ${metalBorder}`}
        style={{ clipPath: PANEL_CLIP }}
      >
        <span aria-hidden className="pointer-events-none absolute inset-0" style={PANEL_FACE} />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-40 mix-blend-soft-light"
          style={PANEL_ORNAMENT}
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[linear-gradient(165deg,rgba(58,41,83,0.35),rgba(36,26,48,0.55))]"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 border border-[#f5ed75]/80 bg-[#7fd8c9] shadow-[0_0_10px_rgba(127,216,201,0.7)]"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-[#fff6a8]/50 to-transparent"
        />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}

export function FantasyTitlePlate({
  kicker,
  title,
  hint,
  onClose,
}: {
  kicker?: string;
  title: string;
  hint?: string;
  onClose?: () => void;
}) {
  return (
    <div className="relative z-10 flex items-start justify-between gap-3 px-3 pt-3">
      <FantasyPanel className="flex-1 !mx-0">
        {kicker ? (
          <p className="text-center text-[10px] font-bold uppercase tracking-[0.28em] text-[#7fd8c9]">{kicker}</p>
        ) : null}
        <h2 className="mt-0.5 text-center font-[family-name:var(--font-display)] text-xl font-extrabold leading-tight text-[#f5ed75] drop-shadow md:text-2xl">
          {title}
        </h2>
        {hint ? (
          <p className="mx-auto mt-1 max-w-[18rem] text-center text-[12px] font-medium leading-snug text-white/85">
            {hint}
          </p>
        ) : null}
      </FantasyPanel>
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          className="relative mt-1 grid h-11 w-11 shrink-0 place-items-center overflow-hidden border border-[#f5ed75]/45 bg-[#241a30] text-xl font-extrabold text-[#f5ed75] shadow-[0_4px_0_#1a1230]"
          aria-label="Закрыть"
          style={{ clipPath: CLOSE_CLIP }}
        >
          <span aria-hidden className="pointer-events-none absolute inset-0 opacity-80" style={buttonFace(3, 3)} />
          <span className="relative z-[1]">×</span>
        </button>
      ) : null}
    </div>
  );
}

type Tone = "gold" | "teal" | "ghost";

const TONE_FACE: Record<Tone, CSSProperties> = {
  gold: buttonFace(0, 0),
  teal: buttonFace(0, 2),
  ghost: buttonFace(0, 3),
};

const TONE_TEXT: Record<Tone, string> = {
  gold: "text-[#241a30]",
  teal: "text-[#13332c]",
  ghost: "text-[#f5ed75]",
};

export function FantasyButton({
  href,
  onClick,
  children,
  tone = "gold",
  className = "",
  type = "button",
}: {
  href?: string;
  onClick?: () => void;
  children: ReactNode;
  tone?: Tone;
  className?: string;
  type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
}) {
  const cls = `relative mx-auto block w-full max-w-[min(92vw,22rem)] min-h-[48px] overflow-hidden border border-[#fff6a8]/25 px-5 py-3 text-center font-[family-name:var(--font-display)] text-base font-extrabold tracking-wide shadow-[0_4px_0_rgba(26,18,48,0.55)] transition active:translate-y-0.5 active:shadow-none ${TONE_TEXT[tone]} ${className}`;
  const style = { clipPath: HEX_CLIP, ...TONE_FACE[tone] } as CSSProperties;
  const inner = (
    <>
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 ${
          tone === "ghost" ? "bg-[linear-gradient(180deg,rgba(58,41,83,0.35),rgba(36,26,48,0.55))]" : "bg-black/10"
        }`}
      />
      <span aria-hidden className="pointer-events-none absolute inset-x-8 top-1 h-1 rounded-sm bg-white/25" />
      <span className="relative z-[1] drop-shadow-sm">{children}</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cls} style={style}>
        {inner}
      </Link>
    );
  }
  return (
    <button type={type} onClick={onClick} className={cls} style={style}>
      {inner}
    </button>
  );
}

export function FantasyStat({
  icon,
  label,
  value,
  highlight = false,
  onClick,
  children,
  className = "",
}: {
  icon?: ReactNode;
  label?: string;
  value?: ReactNode;
  highlight?: boolean;
  onClick?: () => void;
  children?: ReactNode;
  className?: string;
}) {
  const shell = `mx-auto w-full max-w-[min(92vw,22rem)] ${className}`;
  const innerCls = `relative flex w-full items-center gap-3 overflow-hidden border px-3.5 py-2.5 text-left ${
    highlight
      ? "border-[#f5ed75]/70 text-[#241a30]"
      : `bg-[#241a30]/40 text-white ${metalBorder}`
  } ${onClick ? "cursor-pointer transition hover:border-[#f5ed75]/55" : ""}`;
  const style = { clipPath: STAT_CLIP } as const;
  const body = children ? (
    <span className="relative z-[1] w-full">{children}</span>
  ) : (
    <>
      {icon ? <span className="relative z-[1] grid h-9 w-9 shrink-0 place-items-center">{icon}</span> : null}
      <span
        className={`relative z-[1] min-w-0 flex-1 text-sm font-bold ${highlight ? "text-[#241a30]/75" : "text-white/70"}`}
      >
        {label}
      </span>
      <span
        className={`relative z-[1] shrink-0 font-[family-name:var(--font-display)] text-base font-extrabold tabular-nums ${
          highlight ? "text-[#241a30]" : "text-[#f5ed75]"
        }`}
      >
        {value}
      </span>
    </>
  );
  const face = (
    <>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={highlight ? buttonFace(1, 0) : PANEL_FACE}
      />
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 ${
          highlight ? "bg-[#f5ed75]/25" : "bg-[linear-gradient(145deg,rgba(58,41,83,0.55),rgba(36,26,48,0.7))]"
        }`}
      />
      {body}
    </>
  );
  if (onClick) {
    return (
      <div className={shell}>
        <button type="button" onClick={onClick} className={innerCls} style={style}>
          {face}
        </button>
      </div>
    );
  }
  return (
    <div className={shell}>
      <div className={innerCls} style={style}>
        {face}
      </div>
    </div>
  );
}

export function FantasyIcon({
  name,
  className = "",
}: {
  name: "heart" | "streak" | "coin" | "xp" | "star";
  className?: string;
}) {
  const src = `/world/ui/icons/${name}.png`;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" className={`h-8 w-8 object-contain drop-shadow ${className}`} aria-hidden />
  );
}

export function FantasyIconFallback({
  name,
  className = "",
}: {
  name: "heart" | "streak" | "coin" | "xp" | "star";
  className?: string;
}) {
  const paths: Record<typeof name, ReactNode> = {
    heart: (
      <path
        d="M12 21s-7-4.4-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 11c0 5.6-7 10-7 10z"
        fill="url(#fx-heart)"
        stroke="#fff6a8"
        strokeWidth="1"
      />
    ),
    streak: (
      <path
        d="M13 2s-1 4 2 7c0 0-5 1-5 7 0 0 6-2 8-7 0 0-1 5-4 7 4-1 6-5 6-8C20 4 13 2 13 2z"
        fill="url(#fx-flame)"
        stroke="#b8fff2"
        strokeWidth="0.8"
      />
    ),
    coin: (
      <>
        <circle cx="12" cy="12" r="8" fill="url(#fx-coin)" stroke="#fff6a8" strokeWidth="1.2" />
        <circle cx="12" cy="12" r="5" fill="none" stroke="#9a7a18" strokeWidth="1" />
      </>
    ),
    xp: (
      <path d="M13 2 6 13h5l-1 9 8-12h-5l0-8z" fill="url(#fx-bolt)" stroke="#b8fff2" strokeWidth="0.8" />
    ),
    star: (
      <path
        d="M12 2.5l2.4 5.2 5.6.6-4.2 3.8 1.2 5.5L12 15.2 6.9 17.6l1.2-5.5L4 8.3l5.6-.6L12 2.5z"
        fill="url(#fx-coin)"
        stroke="#fff6a8"
        strokeWidth="0.8"
      />
    ),
  };
  return (
    <svg viewBox="0 0 24 24" className={`h-8 w-8 ${className}`} aria-hidden>
      <defs>
        <linearGradient id="fx-heart" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ff8a9a" />
          <stop offset="100%" stopColor="#ee7349" />
        </linearGradient>
        <linearGradient id="fx-flame" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#ee7349" />
          <stop offset="55%" stopColor="#f5ed75" />
          <stop offset="100%" stopColor="#7fd8c9" />
        </linearGradient>
        <linearGradient id="fx-coin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#fff6a8" />
          <stop offset="100%" stopColor="#e8b93e" />
        </linearGradient>
        <linearGradient id="fx-bolt" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#b8fff2" />
          <stop offset="100%" stopColor="#3aa890" />
        </linearGradient>
      </defs>
      {paths[name]}
    </svg>
  );
}

export function BrandIcon({
  name,
  className = "",
}: {
  name: "heart" | "streak" | "coin" | "xp" | "star";
  className?: string;
}) {
  return (
    <span className={`relative inline-grid place-items-center ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/world/ui/icons/${name}.png`}
        alt=""
        className="h-8 w-8 object-contain drop-shadow"
        onError={(e) => {
          e.currentTarget.style.display = "none";
          const sib = e.currentTarget.nextElementSibling as HTMLElement | null;
          if (sib) sib.style.display = "block";
        }}
      />
      <span style={{ display: "none" }}>
        <FantasyIconFallback name={name} />
      </span>
    </span>
  );
}

/** Compact HUD plaque — WorldBar / map header. Uses button atlas tile. */
export function FantasyHudChip({
  icon,
  value,
  gold = false,
  href,
}: {
  icon?: ReactNode;
  value: ReactNode;
  gold?: boolean;
  href?: string;
}) {
  const cls = `relative inline-flex min-h-[40px] items-center gap-1.5 overflow-hidden border px-2.5 py-1 text-sm font-extrabold tabular-nums ${
    gold ? "border-[#fff6a8]/55 text-[#241a30]" : "border-[#f5ed75]/35 text-[#f5ed75]"
  }`;
  const style = {
    clipPath: CHIP_CLIP,
    ...(gold ? buttonFace(0, 0) : buttonFace(0, 3)),
  } as CSSProperties;
  const body = (
    <>
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 ${gold ? "bg-[#f5ed75]/15" : "bg-[#241a30]/35"}`}
      />
      {icon ? <span className="relative z-[1]">{icon}</span> : null}
      <span className="relative z-[1]">{value}</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cls} style={style}>
        {body}
      </Link>
    );
  }
  return (
    <span className={cls} style={style}>
      {body}
    </span>
  );
}

export function FantasyDock({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`relative z-10 mt-auto max-h-[42dvh] animate-[dockUp_280ms_ease-out] overflow-y-auto rounded-t-[26px] border-t-2 border-[#f5ed75]/40 bg-[linear-gradient(180deg,rgba(36,26,48,0.78),rgba(36,26,48,0.96))] px-3 pb-5 pt-4 shadow-[0_-18px_50px_rgba(0,0,0,0.45)] backdrop-blur-md ${className}`}
    >
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-28 opacity-45" style={PLAQUE_FACE} />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#241a30]/20 to-[#241a30]/85"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-2 h-1 w-14 -translate-x-1/2 rounded-sm bg-[#f5ed75]/80"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-[#7fd8c9]/50 to-transparent"
      />
      <div className="relative mx-auto flex max-w-lg flex-col items-stretch gap-2.5 pt-2">{children}</div>
    </div>
  );
}

export type ChromeIconName =
  | "lock"
  | "check"
  | "warning"
  | "info"
  | "audio"
  | "mic"
  | "settings"
  | "back"
  | "forward";

/** Meshy chrome micro-icons under /world/ui/icons/chrome/ (alpha knocked out). */
export function ChromeIcon({
  name,
  className = "h-6 w-6",
}: {
  name: ChromeIconName;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/world/ui/icons/chrome/${name}.png`}
      alt=""
      className={`object-contain drop-shadow ${className}`}
      aria-hidden
    />
  );
}

export function FantasyNavChip({
  children,
  active = false,
  pulse = false,
  onClick,
}: {
  children: ReactNode;
  active?: boolean;
  pulse?: boolean;
  onClick: () => void;
}) {
  const face = pulse ? buttonFace(0, 2) : active ? buttonFace(0, 0) : buttonFace(1, 3);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative min-h-[44px] overflow-hidden whitespace-nowrap border px-4 py-2.5 text-sm font-extrabold transition ${
        pulse
          ? "border-[#7fd8c9]/70 text-[#13332c] shadow-[0_0_0_3px_rgba(127,216,201,0.35)]"
          : active
            ? "border-[#f5ed75]/70 text-[#241a30]"
            : "border-[#f5ed75]/35 text-[#f5ed75]"
      }`}
      style={{ clipPath: CHIP_CLIP, ...face }}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-0 ${
          pulse ? "bg-[#7fd8c9]/20" : active ? "bg-[#f5ed75]/12" : "bg-[#241a30]/40"
        }`}
      />
      <span className="relative z-[1] drop-shadow-sm">{children}</span>
    </button>
  );
}
