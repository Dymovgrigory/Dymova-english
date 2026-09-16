type WashProps = {
  /** Optional cinematic still under the color wash */
  image?: string;
};

export function SkyWash({ image }: WashProps) {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {image ? (
        <>
          <div className="absolute inset-0 bg-cover bg-center opacity-55" style={{ backgroundImage: `url(${image})` }} />
          <div className="absolute inset-0 bg-gradient-to-b from-[#f7f1e4]/25 via-[#f7f1e4]/85 via-35% to-[#f7f1e4]" />
        </>
      ) : null}
      <div className="absolute -left-24 top-[-6rem] h-72 w-72 rounded-full bg-[#f5ed75]/35 blur-3xl" />
      <div className="absolute right-[-4rem] top-24 h-80 w-80 rounded-full bg-[#7fd8c9]/25 blur-3xl" />
      <div className="absolute bottom-10 left-1/3 h-64 w-64 rounded-full bg-[#3a2953]/10 blur-3xl" />
      <div className="world-embers absolute inset-0" />
    </div>
  );
}

export function Burst({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden" aria-hidden>
      {Array.from({ length: 12 }, (_, i) => (
        <span
          key={i}
          className="fx-spark absolute left-1/2 top-1/3 h-2 w-2 rounded-full bg-[#f5ed75]"
          style={{ animationDelay: `${i * 40}ms`, ["--rot" as string]: `${i * 30}deg` }}
        />
      ))}
    </div>
  );
}
