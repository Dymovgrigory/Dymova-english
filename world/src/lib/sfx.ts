/** Короткие звуки урока без отдельных файлов: Web Audio, выключается при reduced-motion. */

function allowed(): boolean {
  if (typeof window === "undefined") return false;
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function beep(freq: number, ms: number, type: OscillatorType = "sine", gain = 0.08) {
  if (!allowed()) return;
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return;
  const ctx = new Ctx();
  const osc = ctx.createOscillator();
  const vol = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  vol.gain.value = gain;
  osc.connect(vol);
  vol.connect(ctx.destination);
  osc.start();
  vol.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + ms / 1000);
  osc.stop(ctx.currentTime + ms / 1000 + 0.02);
}

export function playCorrect() {
  beep(660, 90, "triangle", 0.07);
  window.setTimeout(() => beep(880, 120, "triangle", 0.07), 80);
}

export function playWrong() {
  beep(220, 180, "sawtooth", 0.05);
}

export function playHeart() {
  beep(180, 140, "sine", 0.06);
}
