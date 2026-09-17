/** Оценка «повтори за Foxy»: ребёнок сказал примерно то же самое. */

export function normalizeEcho(text: string): string {
  return (text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function levenshtein(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const grid = Array.from({ length: rows }, () => new Array<number>(cols).fill(0));
  for (let i = 0; i < rows; i += 1) {
    grid[i][0] = i;
  }
  for (let j = 0; j < cols; j += 1) {
    grid[0][j] = j;
  }
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      grid[i][j] = Math.min(grid[i - 1][j] + 1, grid[i][j - 1] + 1, grid[i - 1][j - 1] + cost);
    }
  }
  return grid[a.length][b.length];
}

function contentWords(text: string): string[] {
  return text.split(" ").filter((w) => w.length >= 3);
}

function wordScore(heard: string, want: string): number {
  if (!heard || !want) return 0;
  if (heard === want) return 100;
  if (heard.includes(want) && heard.length >= want.length) return 100;
  if (want.includes(heard) && heard.length >= Math.ceil(want.length * 0.8)) return 100;
  const dist = levenshtein(heard, want);
  const max = Math.max(heard.length, want.length);
  return Math.max(0, Math.round(100 * (1 - dist / max)));
}

export function echoScore(heard: string, target: string): number {
  const a = normalizeEcho(heard);
  const b = normalizeEcho(target);
  if (!a || !b) return 0;
  if (a === b) return 100;
  if (a.includes(b)) return 100;

  const wants = contentWords(b);
  const said = contentWords(a);
  const keys = wants.length ? wants : [b.replace(/ /g, "")];
  const pool = said.length ? said : [a.replace(/ /g, "")];
  const parts = keys.map((want) => Math.max(...pool.map((token) => wordScore(token, want))));
  const covered = parts.reduce((s, n) => s + n, 0) / parts.length;
  const bestWord = Math.max(0, ...parts);
  const whole = wordScore(a.replace(/ /g, ""), b.replace(/ /g, ""));
  return Math.round(Math.max(bestWord, covered, whole * 0.85));
}

export function echoPass(score: number): boolean {
  return score >= 70;
}

/** Говорящие карточки: пока ребёнок не сказал вслух — дальше не пускаем. */
const ECHO_KINDS = new Set(["word_card", "phrase_card", "listen"]);

export function needsEchoFor(kind: string | undefined): boolean {
  return !!kind && ECHO_KINDS.has(kind);
}
