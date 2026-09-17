/** Foxy — маскот Фоксинбурга. Позы сгенерированы по брендбуку: world-pipeline/foxy_poses.py. */

export type FoxyPose = "cheer" | "wave" | "think" | "oops";

export function Foxy({ pose, size = 160, className = "" }: { pose: FoxyPose; size?: number; className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- прозрачный WebP маскота фиксированного размера
    <img
      src={`/content/foxy/${pose}.webp`}
      alt="Foxy"
      width={size}
      height={size}
      className={`select-none object-contain ${className}`}
      draggable={false}
    />
  );
}
