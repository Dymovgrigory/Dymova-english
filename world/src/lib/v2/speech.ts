/** Распознавание английской речи в браузере (Web Speech API). */

type RecognitionResultEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };

type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speechRecognitionSupported(): boolean {
  return recognitionCtor() !== null;
}

/** Слушает одну фразу. Отдаёт все варианты распознавания через пробел, чтобы сервер нашёл совпадение. */
export function listenOnce(timeoutMs = 7000): Promise<string> {
  const Ctor = recognitionCtor();
  if (!Ctor) return Promise.reject(new Error("unsupported"));
  return new Promise((resolve, reject) => {
    const recognition = new Ctor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 3;
    let heard = "";
    const timer = window.setTimeout(() => recognition.stop(), timeoutMs);
    recognition.onresult = (event) => {
      const first = event.results[0];
      heard = Array.from({ length: first.length }, (_, i) => first[i].transcript).join(" ");
    };
    recognition.onerror = (event) => {
      window.clearTimeout(timer);
      reject(new Error(event.error));
    };
    recognition.onend = () => {
      window.clearTimeout(timer);
      resolve(heard);
    };
    recognition.start();
  });
}
