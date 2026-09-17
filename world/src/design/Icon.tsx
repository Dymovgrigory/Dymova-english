/** Набор иконок тренажёра: единая толщина линии 2.2, сетка 24. */

const PATHS = {
  flame: "M12 3c1 3.2 4.6 4.9 4.6 9.3A4.6 4.6 0 0 1 12 17a4.6 4.6 0 0 1-4.6-4.7c0-2 1-3.2 2.1-4.3.2 1.6.9 2.6 2 3 0-3 .1-5.6.5-8z M9.6 20.5h4.8",
  bolt: "M13 2 4.5 13.5H11L10 22l8.5-11.5H12z",
  coin: "M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17z M12 7v10 M14.8 9.2c-.6-.8-1.6-1.2-2.8-1.2-1.6 0-2.8.8-2.8 2s1.2 1.7 2.8 2 2.8.8 2.8 2-1.2 2-2.8 2c-1.2 0-2.2-.4-2.8-1.2",
  path: "M6 20c0-4 12-3 12-8S6 8 6 4 M6 4h.01 M18 12h.01 M6 20h.01",
  dumbbell: "M4 9v6 M7 7v10 M17 7v10 M20 9v6 M7 12h10",
  book: "M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5",
  castle: "M3 21V9l2-1.5L7 9V6l2-1.5L11 6v3h2V6l2-1.5L17 6v3l2-1.5L21 9v12z M10 21v-4a2 2 0 0 1 4 0v4",
  user: "M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9z M3.5 21c.8-4 4.3-6.5 8.5-6.5s7.7 2.5 8.5 6.5",
  speaker: "M4 9.5h3.5L12 5.5v13l-4.5-4H4z M15.5 9a4 4 0 0 1 0 6 M18 6.5a7.5 7.5 0 0 1 0 11",
  check: "M4.5 12.5 9.5 17.5 19.5 6.5",
  close: "M6 6l12 12 M18 6 6 18",
  lock: "M6.5 10.5h11v10h-11z M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5",
  star: "M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z",
  chest: "M3.5 10.5h17v9.5h-17z M3.5 10.5a8.5 5.5 0 0 1 17 0 M11 13h2v3h-2z",
  letters: "M3.5 18 7.5 6l4 12 M5 14h5 M14.5 18V9 M14.5 12.5c0-2 1.3-3.5 3-3.5s3 1.5 3 3.5-1.3 3.5-3 3.5-3-1.5-3-3.5z",
  rule: "M5 4h14v16H5z M8.5 8.5h7 M8.5 12h7 M8.5 15.5h4",
  repeat: "M4 12a8 8 0 0 1 13.7-5.6L20 8.5 M20 4v4.5h-4.5 M20 12a8 8 0 0 1-13.7 5.6L4 15.5 M4 20v-4.5h4.5",
  crown: "M3.5 8 8 12l4-7 4 7 4.5-4-2 11h-13z",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5.5 11.5a6.5 6.5 0 0 0 13 0 M12 18v3",
  back: "M15 5l-7 7 7 7",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9z M12 12h.01",
} as const;

export type IconName = keyof typeof PATHS;

type IconProps = {
  name: IconName;
  size?: number;
  className?: string;
  filled?: boolean;
  title?: string;
};

export function Icon({ name, size = 24, className, filled = false, title }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
