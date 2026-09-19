/** Типы ответов API тренажёра Spotlight (/api/v2). Зеркало world-backend/app/learning. */

export type Band = "starter" | "junior";
export type NodeKind = "words" | "phonics" | "grammar" | "reading" | "chest" | "review" | "module_test";
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
    | "speak"
    | "read_text"
    | "read_text_truefalse"
    | "read_text_answer"
    | "word_in_context";
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
  /** Задания чтения (этап 5): текст и вопросы по нему. */
  text_id?: string;
  title_en?: string;
  sentences?: string[];
  sentence_en?: string;
  q_en?: string;
  q_ru?: string;
};

export type Answer =
  | { index: number }
  | { answer: boolean }
  | { text: string }
  | { tiles: string[] }
  | { pairs: [string, string][] }
  | { transcript: string }
  | { skip: true }
  | Record<string, never>;

export type SessionStart = {
  session_id: string;
  node_id: string;
  kind: NodeKind | "practice" | "trial";
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
  kind: NodeKind | "practice" | "trial";
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
  /** Только у kind="trial": прошёл ли игрок испытание дня. */
  trial_passed?: boolean;
};

export type WordEntry = { id: string; en: string; ru: string; image: string | null; strength: number };
export type WordsBook = { modules: (ModuleSummary & { words: WordEntry[] })[] };

/** Задание Беседки поручений (/api/v2/quests). */
export type Quest = {
  id: string;
  period: "day" | "week";
  title_ru: string;
  progress: number;
  target: number;
  coins: number;
  done: boolean;
  claimed: boolean;
  claimable: boolean;
  spot: string;
  href: string;
};

export type QuestBoard = { daily: Quest[]; weekly: Quest[] };

export type PracticeStatus = { trial_done_today: boolean; trial_available: boolean };
