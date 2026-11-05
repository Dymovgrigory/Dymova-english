"use client";

// Звуки тренажёра (синтез WebAudio — без файлов) и озвучка слов.
import { api } from "@/lib/api";

let ctx: AudioContext | null = null;
const MUTE_KEY = "lk_mute";

export function isMuted(): boolean {
  return typeof window !== "undefined" && window.localStorage.getItem(MUTE_KEY) === "1";
}
export function setMuted(v: boolean): void {
  window.localStorage.setItem(MUTE_KEY, v ? "1" : "0");
}

function tone(freq: number, start: number, dur: number, type: OscillatorType = "sine", vol = 0.18) {
  if (!ctx) return;
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, ctx.currentTime + start);
  g.gain.exponentialRampToValueAtTime(vol, ctx.currentTime + start + 0.015);
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + dur);
  o.connect(g).connect(ctx.destination);
  o.start(ctx.currentTime + start);
  o.stop(ctx.currentTime + start + dur + 0.05);
}

export function sfx(kind: "ok" | "bad" | "tap" | "done" | "level"): void {
  if (typeof window === "undefined" || isMuted()) return;
  try {
    ctx = ctx || new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    if (kind === "ok") { tone(660, 0, 0.12, "triangle"); tone(990, 0.09, 0.22, "triangle"); }
    if (kind === "bad") { tone(220, 0, 0.18, "sawtooth", 0.08); tone(180, 0.12, 0.25, "sawtooth", 0.07); }
    if (kind === "tap") tone(520, 0, 0.06, "sine", 0.08);
    if (kind === "done") [523, 659, 784, 1046].forEach((f, i) => tone(f, i * 0.11, 0.3, "triangle"));
    if (kind === "level") [784, 988, 1175, 1568].forEach((f, i) => tone(f, i * 0.09, 0.35, "square", 0.07));
  } catch {
    /* звук не обязателен */
  }
}

const cache = new Map<string, string>();
let current: HTMLAudioElement | null = null;

/** Озвучка: голос сервера (как в Мире), если недоступен — голос браузера. */
export async function speak(token: string | null, text: string, slow = false): Promise<void> {
  if (typeof window === "undefined" || !text) return;
  try {
    if (!token) throw new Error("no token");
    let url = cache.get(text);
    if (!url) {
      url = await api.speak(token, text);
      cache.set(text, url);
    }
    current?.pause();
    current = new Audio(url);
    current.playbackRate = slow ? 0.7 : 1;
    await current.play();
  } catch {
    if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-GB";
      u.rate = slow ? 0.6 : 0.9;
      const v = window.speechSynthesis.getVoices().find((x) => x.lang.startsWith("en-GB"))
        || window.speechSynthesis.getVoices().find((x) => x.lang.startsWith("en"));
      if (v) u.voice = v;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    }
  }
}
