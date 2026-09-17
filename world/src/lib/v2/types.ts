/** Типы ответов API тренажёра Spotlight (/api/v2). Зеркало world-backend/app/learning. */

export type Band = "starter" | "junior";
export type NodeKind = "words" | "phonics" | "grammar" | "chest" | "review" | "module_test";
export type NodeStatus = "completed" | "current" | "open" | "locked";

export type ModuleSummary = { id: string; order: number; label: string | null; title_en: string; title_ru: string };

export type BookSummary = {
  id: string;
  title: string;
  grade: number;
  cefr: string;
  band: Band;
  modules: ModuleSummary[];
};

export type Courses = { books: BookSummary[] };

export type Profile = { book_id: string; module_id: string; daily_goal_xp: number };

export type CurrentNode = {
  id: string;
  kind: NodeKind;
  book_id: string;
  module_id: string;
  module_title_en: string;
  module_title_ru: string;
};

export type Home = {
  player: { display_name: string; xp: number; coins: number; level: number };
  profile: Profile;
  streak_days: number;
  today_xp: number;
  daily_goal_xp: number;
  goal_reached: boolean;
  current_node: CurrentNode | null;
  due_count: number;
};

export type PathNode = { id: string; kind: NodeKind; status: NodeStatus; stars: number };

export type PathModule = ModuleSummary & { nodes: PathNode[] };

export type LearningPath = {
  book: Omit<BookSummary, "modules">;
  modules: PathModule[];
};

type Option = string | { image?: string; audio?: string };

/** Задание в том виде, в каком его отдаёт сервер (без эталона). Поля зависят от type. */
export type Challenge = {
  index: number;
  type:
    | "teach_word"
    | "teach_rule"
    | "teach_grapheme"
    | "listen_pick_image"
    | "image_pick_word"
    | "read_word_pick_image"
    | "read_phrase_pick_image"
    | "blend_sounds"
    | "translate_pick"
    | "match_pairs"
    | "letter_sound"
    | "sound_letter"
    | "spell_tiles"
    | "build_phrase"
    | "listen_build"
    | "grammar_pick"
    | "type_word"
    | "speak";
  atom_id: string;
  graded: boolean;
  instruction_ru?: string;
  en?: string;
  ru?: string;
  text?: string;
  image?: string | null;
  audio?: string | null;
  reveal_audio?: string;
  options?: Option[];
  tiles?: string[];
  segments?: string[];
  sentence?: string;
  grapheme?: string;
  sound_word?: string;
  direction?: "en_ru" | "ru_en";
  mode?: "audio_image" | "en_ru";
  left?: { id: string; label?: string; audio?: string }[];
  right?: { id: string; label?: string; image?: string }[];
  title_ru?: string;
  rule_ru?: string;
  examples?: { en: string; ru: string }[];
};

export type Answer =
  | { index: number }
  | { text: string }
  | { tiles: string[] }
  | { pairs: [string, string][] }
  | { transcript: string }
  | { skip: true }
  | Record<string, never>;

export type SessionStart = {
  session_id: string;
  node_id: string;
  kind: NodeKind | "practice";
  challenges: Challenge[];
  graded_total: number;
};

export type AnswerReply = {
  correct: boolean;
  typo: boolean;
  skipped: boolean;
  solution: string | null;
  solution_index: number | null;
  requeued: boolean;
  remaining: number;
};

export type SessionResult = {
  node_id: string;
  kind: NodeKind | "practice";
  xp: number;
  coins: number;
  stars: number;
  passed: boolean;
  accuracy: number;
  mistakes: number;
  duration_sec: number;
  streak_days: number;
  today_xp: number;
  daily_goal_xp: number;
  goal_reached: boolean;
  node_completed: boolean;
  next_node_id: string | null;
  player: { xp: number; coins: number; level: number };
  coins_breakdown: Record<string, number>;
  titles_gained: { track: string; level: number; title_ru: string; coins: number }[];
};

export type WordEntry = { id: string; en: string; ru: string; image: string | null; strength: number };
export type WordsBook = { modules: (ModuleSummary & { words: WordEntry[] })[] };
