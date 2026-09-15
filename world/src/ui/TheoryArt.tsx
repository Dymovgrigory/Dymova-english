/** Картинки к теории: буквы, цвета, семья, класс. Без нейросети — читаемые схемы для нуля. */

import type { ReactNode } from "react";

type Props = { id?: string };

function Frame({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <figure className="my-4 overflow-hidden rounded-3xl border border-[#241a30]/10 bg-white p-4">
      <div className="grid min-h-40 place-items-center">{children}</div>
      {label ? <figcaption className="mt-3 text-center text-sm text-[#241a30]/55">{label}</figcaption> : null}
    </figure>
  );
}

function LetterRow({ items }: { items: { L: string; word: string; ru: string }[] }) {
  return (
    <div className="flex flex-wrap justify-center gap-3">
      {items.map((it) => (
        <div key={it.L} className="w-[4.5rem] rounded-2xl bg-[#f7f1e4] p-2 text-center">
          <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold text-[#3a2953]">{it.L}</p>
          <p className="text-xs font-bold">{it.word}</p>
          <p className="text-[10px] text-[#241a30]/50">{it.ru}</p>
        </div>
      ))}
    </div>
  );
}

function Swatch({ color, name }: { color: string; name: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="h-14 w-14 rounded-2xl border border-black/10 shadow-inner" style={{ background: color }} />
      <p className="text-xs font-bold">{name}</p>
    </div>
  );
}

function Person({ title, hue }: { title: string; hue: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <svg viewBox="0 0 64 80" className="h-20 w-16">
        <circle cx="32" cy="18" r="12" fill={hue} />
        <rect x="16" y="32" width="32" height="36" rx="12" fill={hue} />
      </svg>
      <p className="text-xs font-bold">{title}</p>
    </div>
  );
}

export function TheoryArt({ id }: Props) {
  if (!id) return null;
  if (id === "foxi-hello") {
    return (
      <Frame label="Фокси говорит только по-русски, пока ты учишься. Английские слова он показывает на карточках.">
        <p className="text-center text-lg font-extrabold text-[#3a2953]">Привет! Это Фоксинбург.</p>
      </Frame>
    );
  }
  if (id === "letters-ae") {
    return (
      <Frame label="Имя буквы и слово-картинка. Пока не читай как русские буквы.">
        <LetterRow
          items={[
            { L: "A", word: "apple", ru: "яблоко" },
            { L: "B", word: "bag", ru: "сумка" },
            { L: "C", word: "cat", ru: "кот" },
            { L: "D", word: "dog", ru: "пёс" },
            { L: "E", word: "egg", ru: "яйцо" },
          ]}
        />
      </Frame>
    );
  }
  if (id === "letters-st") {
    return (
      <Frame label="S — sun (солнце). T — ten (десять). O — on (на).">
        <LetterRow
          items={[
            { L: "S", word: "sun", ru: "солнце" },
            { L: "T", word: "ten", ru: "десять" },
            { L: "O", word: "on", ru: "на" },
          ]}
        />
      </Frame>
    );
  }
  if (id === "vowels") {
    return (
      <Frame label="Пять гласных. Они «поют». I — ещё и слово «я».">
        <LetterRow
          items={[
            { L: "A", word: "cat", ru: "кот" },
            { L: "E", word: "egg", ru: "яйцо" },
            { L: "I", word: "I", ru: "я" },
            { L: "O", word: "dog", ru: "пёс" },
            { L: "U", word: "sun", ru: "солнце" },
          ]}
        />
      </Frame>
    );
  }
  if (id === "consonants") {
    return (
      <Frame label="Согласные — скелет слова: C-A-T, D-O-G.">
        <div className="flex gap-4 text-center font-[family-name:var(--font-display)] text-3xl font-extrabold">
          <span>C·A·T</span>
          <span>D·O·G</span>
          <span>S·U·N</span>
        </div>
      </Frame>
    );
  }
  if (id === "first-words") {
    return (
      <Frame label="a cat — один кот. an apple / an egg — перед гласным звуком.">
        <LetterRow
          items={[
            { L: "a", word: "cat", ru: "кот" },
            { L: "an", word: "egg", ru: "яйцо" },
            { L: "an", word: "apple", ru: "яблоко" },
          ]}
        />
      </Frame>
    );
  }
  if (id === "hello-hi") {
    return (
      <Frame label="Hello — вежливо. Hi — другу. Оба значат «привет».">
        <div className="flex gap-6 text-center">
          <div>
            <p className="text-2xl font-extrabold">Hello</p>
            <p className="text-sm">учитель, новые люди</p>
          </div>
          <div>
            <p className="text-2xl font-extrabold">Hi</p>
            <p className="text-sm">друг, Фокси</p>
          </div>
        </div>
      </Frame>
    );
  }
  if (id === "my-name") {
    return (
      <Frame label="Сначала вопрос, потом ответ. Каждое английское слово сразу с переводом.">
        <p className="text-center text-lg leading-relaxed">
          <b>What is your name?</b>
          <span className="block text-sm text-[#241a30]/55">Как тебя зовут?</span>
          <b className="mt-3 block">My name is Mia.</b>
          <span className="block text-sm text-[#241a30]/55">Меня зовут Мия.</span>
        </p>
      </Frame>
    );
  }
  if (id === "i-am") {
    return (
      <Frame label="I am = я + есть. «Есть» отдельно не ставим.">
        <p className="text-center font-[family-name:var(--font-display)] text-3xl font-extrabold">I am Foxi.</p>
      </Frame>
    );
  }
  if (id === "please") {
    return (
      <Frame label="Просьба — please. Спасибо — thank you. Отказ — no, thank you.">
        <div className="flex flex-wrap justify-center gap-3 text-sm font-bold">
          <span className="rounded-full bg-[#f5ed75] px-3 py-2">please</span>
          <span className="rounded-full bg-[#7fd8c9] px-3 py-2">thank you</span>
          <span className="rounded-full bg-white px-3 py-2">sorry</span>
        </div>
      </Frame>
    );
  }
  if (id === "bye") {
    return (
      <Frame label="Bye — пока. Goodbye — до свидания. Good morning — доброе утро.">
        <p className="text-center text-2xl font-extrabold">Bye! · Goodbye!</p>
      </Frame>
    );
  }
  if (id === "numbers-15") {
    return (
      <Frame label="Считай вслух, пальцем показывай.">
        <p className="font-[family-name:var(--font-display)] text-2xl font-extrabold tracking-wide">1 2 3 4 5</p>
        <p className="mt-2 text-sm">one two three four five</p>
      </Frame>
    );
  }
  if (id === "numbers-610") {
    return (
      <Frame>
        <p className="font-[family-name:var(--font-display)] text-2xl font-extrabold tracking-wide">6 7 8 9 10</p>
        <p className="mt-2 text-sm">six seven eight nine ten</p>
      </Frame>
    );
  }
  if (id === "how-old") {
    return (
      <Frame label="Возраст: I am + число. Не «I have seven years».">
        <p className="text-center text-xl font-extrabold">
          How old are you?
          <span className="mt-2 block text-base font-semibold text-[#241a30]/55">Сколько тебе лет?</span>
          I am seven.
        </p>
      </Frame>
    );
  }
  if (id === "count") {
    return (
      <Frame label="Let’s count — давай считать. Число стоит перед предметом: two cats.">
        <p className="text-2xl font-extrabold">two cats · three eggs</p>
      </Frame>
    );
  }
  if (id === "how-many") {
    return (
      <Frame label="What number is it? — какое это число?">
        <p className="text-5xl font-extrabold">7</p>
        <p className="text-sm">seven</p>
      </Frame>
    );
  }
  if (id === "color-rb") {
    return (
      <Frame>
        <div className="flex gap-6">
          <Swatch color="#ee7349" name="red" />
          <Swatch color="#5b8def" name="blue" />
        </div>
      </Frame>
    );
  }
  if (id === "color-yg") {
    return (
      <Frame>
        <div className="flex gap-6">
          <Swatch color="#f5ed75" name="yellow" />
          <Swatch color="#7fd8c9" name="green" />
        </div>
      </Frame>
    );
  }
  if (id === "color-more") {
    return (
      <Frame>
        <div className="flex flex-wrap justify-center gap-3">
          <Swatch color="#241a30" name="black" />
          <Swatch color="#fff" name="white" />
          <Swatch color="#8b5a2b" name="brown" />
          <Swatch color="#f4a261" name="orange" />
          <Swatch color="#f4b6c2" name="pink" />
          <Swatch color="#9aa0a6" name="grey" />
        </div>
      </Frame>
    );
  }
  if (id === "what-colour") {
    return (
      <Frame label="Спроси цвет, потом ответь It is…">
        <p className="text-center font-extrabold">
          What colour is it?
          <span className="mt-2 block text-sm font-semibold text-[#241a30]/55">Какого это цвета?</span>
        </p>
      </Frame>
    );
  }
  if (id === "color-noun") {
    return (
      <Frame label="Порядок: a + цвет + вещь.">
        <p className="text-xl font-extrabold">a red ball</p>
      </Frame>
    );
  }
  if (id === "family-parents") {
    return (
      <Frame>
        <div className="flex gap-6">
          <Person title="mum — мама" hue="#ee7349" />
          <Person title="dad — папа" hue="#5b8def" />
        </div>
      </Frame>
    );
  }
  if (id === "family-sibs") {
    return (
      <Frame>
        <div className="flex gap-6">
          <Person title="sister — сестра" hue="#c47aff" />
          <Person title="brother — брат" hue="#7fd8c9" />
        </div>
      </Frame>
    );
  }
  if (id === "this-is") {
    return (
      <Frame label="Показываешь пальцем: This is my…">
        <p className="text-2xl font-extrabold">This is my mum.</p>
      </Frame>
    );
  }
  if (id === "who") {
    return (
      <Frame label="Who — только про людей. What — про вещи.">
        <p className="text-xl font-extrabold">Who is this?</p>
      </Frame>
    );
  }
  if (id === "we-family") {
    return (
      <Frame>
        <div className="flex gap-2">
          <Person title="we" hue="#3a2953" />
          <Person title="are" hue="#ee7349" />
          <Person title="a family" hue="#f5ed75" />
        </div>
      </Frame>
    );
  }
  if (id === "listen-look") {
    return (
      <Frame label="Ухо — listen. Глаз — look.">
        <p className="text-3xl font-extrabold">Listen! · Look!</p>
      </Frame>
    );
  }
  if (id === "sit-stand") {
    return (
      <Frame label="Sit down — вниз на стул. Stand up — вверх.">
        <p className="text-2xl font-extrabold">Sit down · Stand up</p>
      </Frame>
    );
  }
  if (id === "school-things") {
    return (
      <Frame label="book учебник · pen ручка · bag портфель">
        <div className="flex gap-4 text-sm font-extrabold">
          <span className="rounded-xl bg-[#f7f1e4] px-3 py-4">book</span>
          <span className="rounded-xl bg-[#f7f1e4] px-3 py-4">pen</span>
          <span className="rounded-xl bg-[#f7f1e4] px-3 py-4">bag</span>
        </div>
      </Frame>
    );
  }
  if (id === "teacher") {
    return (
      <Frame>
        <Person title="teacher — учитель" hue="#3a2953" />
      </Frame>
    );
  }
  if (id === "lets-start") {
    return (
      <Frame label="Let’s start — давайте начнём урок.">
        <p className="text-2xl font-extrabold">Let’s start!</p>
      </Frame>
    );
  }
  if (id === "wrap") {
    return (
      <Frame label="Это ловушка именно этого урока. Сравни рот с образцом Foxy.">
        <p className="text-lg font-extrabold text-[#3a2953]">Стоп. Проверь звук, не буквы.</p>
      </Frame>
    );
  }
  return null;
}
