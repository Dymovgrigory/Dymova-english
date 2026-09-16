/** Foxy — маскот Фоксинбурга. Позы генерируются по брендбуку (world-pipeline, Meshy). */

export type FoxyPose = "cheer" | "wave" | "think" | "oops";

const POSES: Record<FoxyPose, string> = {
  cheer: "/world/foxi/cheer-prev.png",
  wave: "/world/foxi/cheer-prev.png",
  think: "/world/foxi/cheer-prev.png",
  oops: "/world/foxi/cheer-prev.png",
};

export function Foxy({ pose, size = 160, className = "" }: { pose: FoxyPose; size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- прозрачный PNG маскота фиксированного размера
    <img
      src={POSES[pose]}
      alt="Foxy"
      width={size}
      height={size}
      className={`select-none object-contain ${className}`}
      draggable={false}
    />
  );
}
