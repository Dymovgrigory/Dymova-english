/** Английская озвучка: сначала сервер (Mac say), потом Web Speech. */

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

export async function speakEnglish(text: string): Promise<void> {
  const phrase = (text || "").trim();
  if (!phrase) return;
  currentAudio?.pause();
  if (typeof window !== "undefined") window.speechSynthesis?.cancel();

  const url = `${API}/api/world/tts?q=${encodeURIComponent(phrase.slice(0, 80))}`;
  try {
    const ctrl = new AbortController();
    const kill = window.setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
    window.clearTimeout(kill);
    if (res.ok) {
      const buf = new Uint8Array(await res.arrayBuffer());
      const riff = buf.length > 8000 && buf[0] === 82 && buf[1] === 73 && buf[2] === 70 && buf[3] === 70;
      if (riff) {
        const src = URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
        const audio = new Audio(src);
        currentAudio = audio;
        await new Promise<void>((resolve, reject) => {
          const done = () => {
            URL.revokeObjectURL(src);
            resolve();
          };
          audio.addEventListener("ended", done, { once: true });
          audio.addEventListener("error", () => reject(new Error("play")), { once: true });
          window.setTimeout(done, 8000);
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
    utter.pitch = 1.18;
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
