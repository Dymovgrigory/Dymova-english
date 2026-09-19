import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnswerReply, Challenge } from "@/lib/v2/types";

import { ReadAnswer, ReadText, ReadTrueFalse, TextToggle, WordInContext } from "./readingViews";

vi.mock("@/lib/speak", () => ({
  speakEnglish: vi.fn(() => Promise.resolve()),
  stopSpeaking: vi.fn(),
}));

const reply = (over: Partial<AnswerReply> = {}): AnswerReply => ({
  correct: true,
  typo: false,
  skipped: false,
  solution: null,
  solution_index: null,
  requeued: false,
  remaining: 0,
  ...over,
});

const base: Pick<Challenge, "index" | "atom_id" | "graded"> = { index: 0, atom_id: "sp2.m1.t1", graded: true };

const viewProps = {
  draft: null,
  locked: false,
  reveal: null,
  onDraft: () => {},
};

describe("ReadText — книжный разворот", () => {
  const challenge: Challenge = {
    ...base,
    type: "read_text",
    graded: false,
    text_id: "sp2.m1.t1",
    title_en: "Foxy at School",
    title_ru: "Фокси в школе",
    sentences: ["Foxy runs to school.", "He likes books.", "His bag is red."],
  };

  it("показывает заголовок, предложения и кнопки «Слушать» / «Я прочитал(а)»", () => {
    render(<ReadText {...viewProps} challenge={challenge} />);
    expect(screen.getByRole("region", { name: "Книжный разворот" })).toBeInTheDocument();
    expect(screen.getByText("Foxy at School")).toBeInTheDocument();
    expect(screen.getByText("He likes books.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Слушать/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Я прочитал(а)" })).toBeInTheDocument();
  });

  it("«Я прочитал(а)» отправляет пустой ответ (шаг неоцениваемый)", () => {
    const onSubmit = vi.fn();
    render(<ReadText {...viewProps} challenge={challenge} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: "Я прочитал(а)" }));
    expect(onSubmit).toHaveBeenCalledWith({});
  });

  it("«Слушать» озвучивает предложения по очереди", async () => {
    const { speakEnglish } = await import("@/lib/speak");
    render(<ReadText {...viewProps} challenge={challenge} />);
    fireEvent.click(screen.getByRole("button", { name: /Слушать/ }));
    await screen.findByRole("button", { name: /Слушать/ });
    await vi.waitFor(() => expect(speakEnglish).toHaveBeenCalledTimes(3));
    expect(vi.mocked(speakEnglish).mock.calls[0][0]).toBe("Foxy runs to school.");
  });
});

describe("TextToggle — «Показать текст»", () => {
  it("свернут по умолчанию и раскрывается с aria-expanded", () => {
    render(<TextToggle sentences={["One.", "Two."]} />);
    const toggle = screen.getByRole("button", { name: "Показать текст" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: "Текст для чтения" })).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Скрыть текст" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "Текст для чтения" })).toHaveTextContent("One.");
  });
});

describe("ReadTrueFalse", () => {
  const challenge: Challenge = {
    ...base,
    type: "read_text_truefalse",
    text_id: "sp2.m1.t1",
    sentence_en: "Foxy likes books.",
    q_ru: "Фокси нравятся книги.",
    sentences: ["Foxy likes books."],
  };

  it("крупные кнопки «Правда»/«Неправда» ставят черновик {answer}", () => {
    const onDraft = vi.fn();
    render(<ReadTrueFalse {...viewProps} challenge={challenge} onDraft={onDraft} />);
    fireEvent.click(screen.getByRole("button", { name: "Правда" }));
    expect(onDraft).toHaveBeenCalledWith({ answer: true });
    fireEvent.click(screen.getByRole("button", { name: "Неправда" }));
    expect(onDraft).toHaveBeenCalledWith({ answer: false });
  });

  it("текст доступен во время ответа через «Показать текст»", () => {
    render(<ReadTrueFalse {...viewProps} challenge={challenge} />);
    fireEvent.click(screen.getByRole("button", { name: "Показать текст" }));
    expect(screen.getByRole("region", { name: "Текст для чтения" })).toBeInTheDocument();
  });

  it("раскрытие: верная кнопка зелёная, неверный выбор красный", () => {
    render(
      <ReadTrueFalse
        {...viewProps}
        challenge={challenge}
        draft={{ answer: false }}
        locked
        reveal={reply({ correct: false, solution: "true" })}
      />,
    );
    expect(screen.getByRole("button", { name: "Правда" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Неправда" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("ReadAnswer — выбор из трёх", () => {
  const challenge: Challenge = {
    ...base,
    type: "read_text_answer",
    text_id: "sp2.m1.t1",
    q_en: "What does Foxy like?",
    q_ru: "Что Фокси нравится?",
    options: ["books", "cats", "milk"],
  };

  it("показывает вопрос и три варианта, выбор → onDraft({index})", () => {
    const onDraft = vi.fn();
    render(<ReadAnswer {...viewProps} challenge={challenge} onDraft={onDraft} />);
    expect(screen.getByText("What does Foxy like?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cats/ }));
    expect(onDraft).toHaveBeenCalledWith({ index: 1 });
  });
});

describe("WordInContext — слово в пропуске", () => {
  const challenge: Challenge = {
    ...base,
    type: "word_in_context",
    text_id: "sp2.m1.t1",
    sentence_en: "Foxy has a red ___.",
    options: ["bag", "cat", "pen"],
  };

  it("показывает пропуск и варианты слов", () => {
    render(<WordInContext {...viewProps} challenge={challenge} />);
    expect(screen.getByText(/Foxy has a red/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pen/ })).toBeInTheDocument();
  });

  it("выбранное слово встаёт в пропуск", () => {
    render(<WordInContext {...viewProps} challenge={challenge} draft={{ index: 0 }} />);
    // Слово появляется дважды: в пропуске предложения и среди вариантов.
    expect(screen.getAllByText("bag")).toHaveLength(2);
  });
});
