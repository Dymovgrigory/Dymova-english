export function HeartMark({ on, onDark = false }: { on: boolean; onDark?: boolean }) {
  const fill = on ? "#ee7349" : onDark ? "rgba(255,255,255,0.2)" : "rgba(36,26,48,0.18)";
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill={fill} aria-hidden>
      <path d="M12 20.4S3.2 14.8 3.2 8.9A4.7 4.7 0 0 1 12 6.4a4.7 4.7 0 0 1 8.8 2.5c0 5.9-8.8 11.5-8.8 11.5z" />
    </svg>
  );
}

export function Hearts({ count, max = 5, onDark = false }: { count: number; max?: number; onDark?: boolean }) {
  return (
    <span className="flex items-center gap-0.5" aria-label={`${count} из ${max} сердец`}>
      {Array.from({ length: max }, (_, i) =>
        i < count ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={i}
            src="/world/ui/icons/heart.png"
            alt=""
            className="fx-heart h-5 w-5 object-contain drop-shadow"
          />
        ) : (
          <HeartMark key={i} on={false} onDark={onDark} />
        ),
      )}
    </span>
  );
}

export function Stars({ count, onDark = false }: { count: number; onDark?: boolean }) {
  const empty = onDark ? "rgba(255,255,255,0.2)" : "rgba(36,26,48,0.18)";
  return (
    <span className="flex justify-center gap-0.5" aria-hidden>
      {Array.from({ length: 3 }, (_, i) => (
        <svg key={i} viewBox="0 0 24 24" className="h-3.5 w-3.5" fill={i < count ? (onDark ? "#f5ed75" : "#241a30") : empty}>
          <path d="M12 2.4 14.6 9H21l-5.2 4 2 6.6L12 16.2 6.2 19.6l2-6.6L3 9h6.4z" />
        </svg>
      ))}
    </span>
  );
}

export function LockMark() {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/world/ui/icons/chrome/lock.png"
      alt=""
      className="h-8 w-8 object-contain opacity-90 drop-shadow"
      aria-hidden
    />
  );
}

export function GateMark({ light = false }: { light?: boolean }) {
  const stroke = light ? "#f5ed75" : "#241a30";
  return (
    <svg viewBox="0 0 24 24" className="h-9 w-9 fill-none" stroke={stroke} strokeWidth="2" aria-hidden>
      <path d="M4 20V10l8-6 8 6v10" />
      <path d="M10 20v-6h4v6" />
    </svg>
  );
}

export function KeyMark({ light = false }: { light?: boolean }) {
  const stroke = light ? "#f5ed75" : "#241a30";
  return (
    <svg viewBox="0 0 24 24" className="h-9 w-9 fill-none" stroke={stroke} strokeWidth="2" aria-hidden>
      <circle cx="8" cy="10" r="4" />
      <path d="M12 10h9v3h-2v3h-3v-3h-1" />
    </svg>
  );
}

function SpotSvg({ d, light }: { d: string; light: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className="h-9 w-9 fill-none" stroke={light ? "#f5ed75" : "#241a30"} strokeWidth="2" aria-hidden>
      <path d={d} />
    </svg>
  );
}

export function SpotIcon({
  kind,
  index,
  locked,
  light = false,
}: {
  kind?: string;
  index: number;
  locked?: boolean;
  light?: boolean;
}) {
  if (locked) return <LockMark />;
  if (kind === "checkpoint") return <KeyMark light={light} />;
  const spots = [
    <GateMark key="g" light={light} />,
    <SpotSvg key="b" light={light} d="M3 16h18M5 16c2-6 4-6 6 0 2-6 4-6 6 0 2-6 3-6 2 0" />,
    <SpotSvg key="s" light={light} d="M12 3v18M3 12h18M6 6l12 12M18 6 6 18" />,
    <SpotSvg key="l" light={light} d="M9 21h6M12 3a5 5 0 0 1 5 5c0 3-2 4.5-3 6H10c-1-1.5-3-3-3-6a5 5 0 0 1 5-5z" />,
    <SpotSvg key="h" light={light} d="M12 3 5 7v5c0 5 3 8 7 9 4-1 7-4 7-9V7z" />,
  ];
  return spots[index] ?? spots[2];
}

export function UnitMark({ id, dark }: { id: string; dark?: boolean }) {
  return (
    <span
      className={`mr-2 inline-grid h-7 w-7 place-items-center rounded-lg text-xs font-extrabold ${
        dark ? "bg-[#f5ed75]/15 text-[#f5ed75]" : "bg-[#241a30]/12 text-[#241a30]"
      }`}
      aria-hidden
    >
      {id.slice(0, 1).toUpperCase()}
    </span>
  );
}
