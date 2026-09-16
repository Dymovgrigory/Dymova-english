/** Английская озвучка: сервер (edge-tts / say) → Web Speech только если API молчит. */

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");

let voicesReady: Promise<void> | null = null;

function waitVoices(): Promise<void> {
  if (typeof window === "undefined" || !window.speechSynthesis) return Promise.resolve();
  if (voicesReady) return voicesReady;
  voicesReady = new Promise((resolve) => {
    const done = () => resolve();
    const voices = window.speechSynthesis.getVoices();
    if (voices.length) {
      done();
      return;
    }
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    window.setTimeout(done, 800);
  });
  return voicesReady;
}

function pickEnglishVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis?.getVoices() ?? [];
  return (
    voices.find((v) => /samantha/i.test(v.name)) ||
    voices.find((v) => /en-US/i.test(v.lang) && /samantha|kathy|karen/i.test(v.name)) ||
    voices.find((v) => /^en(-|$)/i.test(v.lang)) ||
    voices.find((v) => /english/i.test(v.name))
  );
}

let currentAudio: HTMLAudioElement | null = null;

function sniffAudioType(buf: Uint8Array, headerType: string | null): string | null {
  if (buf.length > 3 && buf[0] === 82 && buf[1] === 73 && buf[2] === 70 && buf[3] === 70) return "audio/wav";
  if (buf.length > 2 && buf[0] === 0xff && (buf[1] & 0xe0) === 0xe0) return "audio/mpeg";
  if (buf.length > 2 && buf[0] === 0x49 && buf[1] === 0x44 && buf[2] === 0x33) return "audio/mpeg";
  if (headerType?.includes("mpeg") || headerType?.includes("mp3")) return "audio/mpeg";
  if (headerType?.includes("wav")) return "audio/wav";
  return null;
}

export async function speakEnglish(text: string): Promise<void> {
  const phrase = (text || "").trim();
  if (!phrase) return;
  currentAudio?.pause();
  if (typeof window !== "undefined") window.speechSynthesis?.cancel();

  const url = `${API}/api/world/tts?q=${encodeURIComponent(phrase.slice(0, 80))}`;
  try {
    const ctrl = new AbortController();
    const kill = window.setTimeout(() => ctrl.abort(), 8000);
    let player = "guest";
    try {
      player =
        window.localStorage.getItem("world.playerToken") ||
        window.localStorage.getItem("world.playerKey") ||
        "guest";
    } catch {
      /* private mode */
    }
    const res = await fetch(url, {
      signal: ctrl.signal,
      cache: "no-store",
      headers: { "X-World-Player": player },
    });
    window.clearTimeout(kill);
    if (res.ok) {
      const buf = new Uint8Array(await res.arrayBuffer());
      const mime = sniffAudioType(buf, res.headers.get("content-type"));
      if (mime && buf.length > 1500) {
        const src = URL.createObjectURL(new Blob([buf], { type: mime }));
        const audio = new Audio(src);
        currentAudio = audio;
        await new Promise<void>((resolve, reject) => {
          const done = () => {
            URL.revokeObjectURL(src);
            resolve();
          };
          audio.addEventListener("ended", done, { once: true });
          audio.addEventListener("error", () => reject(new Error("play")), { once: true });
          window.setTimeout(done, 12000);
          void audio.play().catch(reject);
        });
        return;
      }
    }
  } catch {
    /* Web Speech fallback */
  }

  await waitVoices();
  if (!window.speechSynthesis) return;
  await new Promise<void>((resolve) => {
    const utter = new SpeechSynthesisUtterance(phrase);
    utter.lang = "en-US";
    utter.rate = 0.9;
    utter.pitch = 1.05;
    const voice = pickEnglishVoice();
    if (voice) utter.voice = voice;
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    window.setTimeout(() => window.speechSynthesis.speak(utter), 40);
    window.setTimeout(resolve, 4000);
  });
}

export function stopSpeaking() {
  currentAudio?.pause();
  currentAudio = null;
  if (typeof window !== "undefined") window.speechSynthesis?.cancel();
}

export function playClip(src?: string, fallback?: string) {
  if (src) {
    const audio = new Audio(src);
    audio.play().catch(() => {
      void speakEnglish(fallback || "");
    });
    return;
  }
  void speakEnglish(fallback || "");
}
