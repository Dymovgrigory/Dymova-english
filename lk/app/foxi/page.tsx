"use client";

// «Мой Фокси» — редактор персонажа в духе Sims: настоящий 3D-маскот Фоксинбурга (та же модель,
// что в Мире), живой и анимированный. Движок — /public/foxi3d/foxi-studio.js (three.js лежит
// в /public/vendor/three, в сборку остальных страниц не попадает). Облик хранится за учеником.
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import "./fs.css";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api, FoxiLook } from "@/lib/api";
import {
  Backpack, Camera, Crown, Download, Footprints, Glasses, Hand, Image as ImageIcon, Megaphone, Palette,
  PartyPopper, PersonStanding, Ribbon, Rocket, RotateCw, Save, ScanFace, Scissors, Shirt, Shuffle, Sparkles, Undo2,
} from "lucide-react";

const STUDIO_URL = "/foxi3d/foxi-studio.js";

type Studio = {
  set: (look: FoxiLook) => void;
  play: (anim: string) => void;
  focus: (view: "body" | "face") => void;
  turntable: (on: boolean) => void;
  snapshot: () => string;
  dispose: () => void;
};

const BASE: FoxiLook = {
  fur: "#c4652a", eyes: "#568698", top: "#d6b85e", pattern: "none", patternColor: "#6a3fc4", logo: true,
  bottom: "#421b5f", bag: "#421b5f", shoes: "#421b5f", hat: "none", hatColor: "#e2533c", hair: "none",
  glasses: "none", neck: "none", neckColor: "#e2533c", back: "none", scene: "room",
};

type L = [string, string];   // [ru, en]
const FUR: [string, L][] = [
  ["#c4652a", ["Рыжий", "Ginger"]], ["#a8401c", ["Огненный", "Fiery"]], ["#d99a3c", ["Золотой", "Golden"]],
  ["#f2efe9", ["Полярный", "Arctic"]], ["#9aa3ad", ["Серебряный", "Silver"]], ["#6b4128", ["Шоколадный", "Chocolate"]],
  ["#2d2a35", ["Ночной", "Night"]], ["#e889b0", ["Розовый", "Pink"]], ["#5aa0d8", ["Небесный", "Sky"]], ["#8a6ad6", ["Волшебный", "Magic"]],
];
const EYES: [string, L][] = [
  ["#568698", ["Голубые", "Blue"]], ["#6b3b1c", ["Карие", "Brown"]], ["#2f8f4e", ["Зелёные", "Green"]],
  ["#7b4fd6", ["Фиолетовые", "Violet"]], ["#d18a12", ["Янтарные", "Amber"]], ["#d6445c", ["Рубиновые", "Ruby"]],
];
const COLORS = ["#d6b85e", "#f4f1ea", "#e2533c", "#ef6aa8", "#e2a019", "#2fa86b", "#22b3b0", "#3a7bd5", "#6a3fc4", "#421b5f", "#1f2a44", "#2b2b2b"];

const HATS: [string, L][] = [
  ["none", ["Без шапки", "None"]], ["cap", ["Кепка", "Cap"]], ["beanie", ["Шапка с помпоном", "Beanie"]], ["wizard", ["Шляпа волшебника", "Wizard hat"]],
  ["crown", ["Корона", "Crown"]], ["tophat", ["Цилиндр", "Top hat"]], ["party", ["Праздничный колпак", "Party hat"]],
  ["headphones", ["Наушники", "Headphones"]], ["flower", ["Цветок", "Flower"]], ["halo", ["Нимб", "Halo"]],
];
const HAIR: [string, L][] = [["none", ["Как есть", "Natural"]], ["tuft", ["Хохолок", "Tuft"]], ["spiky", ["Ёжик", "Spiky"]], ["mohawk", ["Ирокез", "Mohawk"]], ["curly", ["Кудряшки", "Curly"]]];
const GLASSES: [string, L][] = [["none", ["Без очков", "None"]], ["round", ["Круглые", "Round"]], ["gold", ["Золотые", "Gold"]], ["sun", ["Солнечные", "Sunglasses"]], ["star", ["Звёздочки", "Stars"]]];
const PATTERNS: [string, L][] = [["none", ["Однотонная", "Plain"]], ["stripes", ["Полоски", "Stripes"]], ["dots", ["Горошек", "Dots"]], ["checks", ["Клетка", "Checks"]], ["stars", ["Звёзды", "Stars"]], ["zigzag", ["Зигзаг", "Zigzag"]]];
const NECK: [string, L][] = [["none", ["Нет", "None"]], ["scarf", ["Шарф", "Scarf"]], ["bowtie", ["Бабочка", "Bow tie"]], ["tie", ["Галстук", "Tie"]], ["medal", ["Медаль", "Medal"]]];
const BACK: [string, L][] = [["none", ["Нет", "None"]], ["cape", ["Плащ героя", "Hero cape"]], ["wings", ["Крылышки", "Wings"]]];
const SCENES: [string, L][] = [["room", ["Комната", "Room"]], ["castle", ["Замок", "Castle"]], ["forest", ["Лес", "Forest"]], ["space", ["Космос", "Space"]], ["beach", ["Пляж", "Beach"]], ["snow", ["Зима", "Winter"]]];

const PRESETS: [string, L, FoxiLook][] = [
  ["school", ["Школьник", "Student"], { ...BASE }],
  ["wizard", ["Волшебник", "Wizard"], { ...BASE, top: "#3a2a8c", pattern: "stars", patternColor: "#ffd36e", hat: "wizard", hatColor: "#3a2a8c", glasses: "round", back: "cape", neckColor: "#6a3fc4", scene: "castle" }],
  ["king", ["Король", "King"], { ...BASE, top: "#e2533c", hat: "crown", back: "cape", neckColor: "#c0392b", neck: "medal", scene: "castle" }],
  ["hero", ["Супергерой", "Superhero"], { ...BASE, top: "#3a7bd5", logo: false, bottom: "#e2533c", shoes: "#e2533c", back: "cape", neckColor: "#e2533c", glasses: "sun", scene: "space" }],
  ["winter", ["Зимний", "Winter"], { ...BASE, top: "#f4f1ea", pattern: "zigzag", patternColor: "#e2533c", hat: "beanie", hatColor: "#e2533c", neck: "scarf", neckColor: "#e2533c", scene: "snow" }],
  ["beach", ["Пляжный", "Beach"], { ...BASE, top: "#22b3b0", pattern: "dots", patternColor: "#f4f1ea", glasses: "sun", hat: "cap", hatColor: "#e2a019", bottom: "#e2a019", scene: "beach" }],
  ["party", ["Праздник", "Party"], { ...BASE, top: "#ef6aa8", pattern: "checks", patternColor: "#f4f1ea", hat: "party", hatColor: "#6a3fc4", glasses: "star", neck: "bowtie", neckColor: "#6a3fc4", back: "wings", scene: "room" }],
];

const MOVES: [string, L, typeof Hand][] = [
  ["wave", ["Привет!", "Hi!"], Hand], ["cheer", ["Ура!", "Hooray!"], PartyPopper], ["jump", ["Прыжок", "Jump"], Rocket],
  ["dance", ["Танец", "Dance"], Sparkles], ["walk", ["Шагать", "Walk"], Footprints], ["call", ["Позвать", "Call"], Megaphone],
];

type Cat = "presets" | "fur" | "head" | "face" | "top" | "bottom" | "extras" | "scene";
const CATS: [Cat, L, typeof Hand][] = [
  ["presets", ["Образы", "Looks"], Sparkles], ["fur", ["Окрас", "Fur"], Palette], ["head", ["Голова", "Head"], Crown],
  ["face", ["Очки и глаза", "Eyes"], Glasses], ["top", ["Футболка", "T-shirt"], Shirt], ["bottom", ["Шорты и кеды", "Shorts & shoes"], Footprints],
  ["extras", ["Аксессуары", "Extras"], Ribbon], ["scene", ["Фон", "Scene"], ImageIcon],
];

function H({ children }: { children: ReactNode }) {
  return <h3 className="fs-h">{children}</h3>;
}

export default function FoxiPage() {
  return (
    <CabinetPage>
      <FoxiStudio />
    </CabinetPage>
  );
}

function FoxiStudio() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const t = (l: L) => (ru ? l[0] : l[1]);
  const { token, studentId, active } = useCabinet();
  const canvas = useRef<HTMLCanvasElement>(null);
  const studio = useRef<Studio | null>(null);
  const [look, setLook] = useState<FoxiLook>(BASE);
  const [cat, setCat] = useState<Cat>("presets");
  const [state, setState] = useState<"loading" | "ready" | "nogl">("loading");
  const [saved, setSaved] = useState<"" | "saving" | "ok" | "err">("");
  const [view, setView] = useState<"body" | "face">("body");
  const [spin, setSpin] = useState(false);
  const history = useRef<FoxiLook[]>([]);

  useEffect(() => {
    if (!token || !active) return;
    api.foxi(token, studentId).then((r) => { if (r.foxi) setLook({ ...BASE, ...r.foxi }); }).catch(() => undefined);
  }, [token, active, studentId]);

  useEffect(() => {
    let cancelled = false;
    const el = canvas.current;
    if (!el) return;
    const gl = (() => { try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; } })();
    if (!gl) { setState("nogl"); return; }
    import(/* webpackIgnore: true */ /* turbopackIgnore: true */ STUDIO_URL)
      .then(async (m: { createFoxiStudio: (c: HTMLCanvasElement, l: FoxiLook) => Promise<Studio> }) => {
        const s = await m.createFoxiStudio(el, look);
        if (cancelled) { s.dispose(); return; }
        studio.current = s;
        setState("ready");
        s.play("wave");
      })
      .catch(() => { if (!cancelled) setState("nogl"); });
    return () => { cancelled = true; studio.current?.dispose(); studio.current = null; };
    // сцена создаётся один раз, дальше облик меняется через set()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { studio.current?.set(look); setSaved(""); }, [look, state]);

  const change = useCallback((patch: FoxiLook, react?: string) => {
    setLook((l) => { history.current = [...history.current.slice(-30), l]; return { ...l, ...patch }; });
    if (react) studio.current?.play(react);
  }, []);
  const undo = () => { const prev = history.current.pop(); if (prev) setLook(prev); };

  const random = () => {
    const any = <T,>(a: T[]) => a[Math.floor(Math.random() * a.length)];
    change({
      fur: any(FUR)[0], eyes: any(EYES)[0], top: any(COLORS), pattern: any(PATTERNS)[0], patternColor: any(COLORS),
      bottom: any(COLORS), bag: any(COLORS), shoes: any(COLORS), hat: any(HATS)[0], hatColor: any(COLORS), hair: any(HAIR)[0],
      glasses: Math.random() < 0.5 ? "none" : any(GLASSES)[0], neck: any(NECK)[0], neckColor: any(COLORS), back: Math.random() < 0.7 ? "none" : any(BACK)[0],
    }, "cheer");
  };

  const save = async () => {
    if (!token) return;
    setSaved("saving");
    try { await api.saveFoxi(token, studentId, look); setSaved("ok"); studio.current?.play("jump"); }
    catch { setSaved("err"); }
  };

  const photo = () => {
    const url = studio.current?.snapshot();
    if (!url) return;
    const a = document.createElement("a");
    a.href = url; a.download = `${(look.name || "foxi").replace(/[^\p{L}\p{N}_-]+/gu, "-")}.png`; a.click();
  };

  const swatches = (key: keyof FoxiLook, list: (string | [string, L])[], react?: string) => (
    <div className="fs-swatches">
      {list.map((item) => {
        const [value, label] = typeof item === "string" ? [item, [item, item] as L] : item;
        const on = look[key] === value;
        return (
          <button key={value} type="button" className={"fs-swatch" + (on ? " is-on" : "")} style={{ background: value }}
            onClick={() => change({ [key]: value } as FoxiLook, react)} aria-pressed={on} aria-label={t(label)} title={t(label)} />
        );
      })}
      <label className="fs-swatch fs-swatch-custom" title={ru ? "Свой цвет" : "Custom colour"}>
        <input type="color" value={String(look[key] ?? "#ffffff")} onChange={(e) => change({ [key]: e.target.value } as FoxiLook)} />
      </label>
    </div>
  );
  const chips = (key: keyof FoxiLook, list: [string, L][], react?: string) => (
    <div className="fs-chips">
      {list.map(([value, label]) => (
        <button key={value} type="button" className={"fs-chip" + (look[key] === value ? " is-on" : "")} aria-pressed={look[key] === value}
          onClick={() => change({ [key]: value } as FoxiLook, react)}>{t(label)}</button>
      ))}
    </div>
  );

  return (
    <div className={`fs fs-scene-${look.scene ?? "room"}`}>
      <section className="fs-stage">
        <div className="fs-backdrop" aria-hidden />
        <canvas ref={canvas} className="fs-canvas" aria-label={ru ? "Твой Фокси. Покрути его пальцем или мышкой" : "Your Foxi. Drag to turn him around"} />
        {state === "loading" && <div className="fs-loading"><span className="fs-spinner" />{ru ? "Фокси собирается в студию…" : "Foxi is coming to the studio…"}</div>}
        {state === "nogl" && (
          <div className="fs-loading">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/foxi/guide.webp" alt="" width={150} height={246} />
            <p>{ru ? "Этот браузер не показывает 3D. Выбор всё равно сохранится." : "This browser can't show 3D, but your choices still save."}</p>
          </div>
        )}

        <div className="fs-plate">
          <input value={look.name ?? ""} maxLength={24} placeholder={ru ? "Имя Фокси" : "Foxi's name"}
            onChange={(e) => setLook((l) => ({ ...l, name: e.target.value }))} aria-label={ru ? "Имя твоего Фокси" : "Your Foxi's name"} />
        </div>

        <div className="fs-cam">
          <button type="button" className={view === "body" ? "is-on" : ""} onClick={() => { setView("body"); studio.current?.focus("body"); }} title={ru ? "Весь рост" : "Full body"}><PersonStanding size={18} /></button>
          <button type="button" className={view === "face" ? "is-on" : ""} onClick={() => { setView("face"); studio.current?.focus("face"); }} title={ru ? "Мордочка крупно" : "Close-up"}><ScanFace size={18} /></button>
          <button type="button" className={spin ? "is-on" : ""} onClick={() => { setSpin(!spin); studio.current?.turntable(!spin); }} title={ru ? "Крутить" : "Spin"}><RotateCw size={18} /></button>
          <button type="button" onClick={photo} title={ru ? "Сфотографировать" : "Take a photo"} disabled={state !== "ready"}><Camera size={18} /></button>
        </div>

        <div className="fs-moves" role="toolbar" aria-label={ru ? "Что сделать Фокси" : "Make Foxi move"}>
          {MOVES.map(([id, label, Icon]) => (
            <button key={id} type="button" onClick={() => studio.current?.play(id)} disabled={state !== "ready"}>
              <Icon size={18} strokeWidth={2.4} /><span>{t(label)}</span>
            </button>
          ))}
        </div>
      </section>

      <aside className="fs-panel">
        <nav className="fs-rail" aria-label={ru ? "Разделы" : "Sections"}>
          {CATS.map(([id, label, Icon]) => (
            <button key={id} type="button" className={cat === id ? "is-on" : ""} aria-pressed={cat === id} onClick={() => setCat(id)} title={t(label)}>
              <Icon size={20} strokeWidth={2.3} /><span>{t(label)}</span>
            </button>
          ))}
        </nav>

        <div className="fs-body">
          {cat === "presets" && (
            <>
              <H>{ru ? "Готовые образы" : "Ready looks"}</H>
              <div className="fs-presets">
                {PRESETS.map(([id, label, preset]) => (
                  <button key={id} type="button" className="fs-preset" onClick={() => change({ ...preset, name: look.name }, "cheer")}>
                    <span className="fs-preset-dot" style={{ background: `linear-gradient(135deg, ${preset.top} 0 50%, ${preset.hatColor} 50% 100%)` }} />
                    {t(label)}
                  </button>
                ))}
              </div>
              <p className="fs-tip">{ru ? "Выбери образ, а потом поменяй что хочешь — цвета, шапку, очки, узор." : "Pick a look, then change anything you like."}</p>
            </>
          )}
          {cat === "fur" && (<><H>{ru ? "Цвет шерсти" : "Fur colour"}</H>{swatches("fur", FUR, "wave")}</>)}
          {cat === "head" && (
            <>
              <H>{ru ? "Головной убор" : "Hat"}</H>{chips("hat", HATS, "cheer")}
              {look.hat !== "none" && look.hat !== "crown" && look.hat !== "halo" && (<><H>{ru ? "Цвет" : "Colour"}</H>{swatches("hatColor", COLORS)}</>)}
              <H>{ru ? "Причёска" : "Hair"}</H>{chips("hair", HAIR)}
              {!["none", "headphones", "flower", "halo"].includes(look.hat ?? "none") && <p className="fs-tip">{ru ? "Под шапкой причёску не видно." : "The hat hides the hair."}</p>}
            </>
          )}
          {cat === "face" && (<><H>{ru ? "Очки" : "Glasses"}</H>{chips("glasses", GLASSES, "wave")}<H>{ru ? "Цвет глаз" : "Eye colour"}</H>{swatches("eyes", EYES)}</>)}
          {cat === "top" && (
            <>
              <H>{ru ? "Цвет футболки" : "T-shirt colour"}</H>{swatches("top", COLORS)}
              <H>{ru ? "Узор" : "Pattern"}</H>{chips("pattern", PATTERNS)}
              {look.pattern !== "none" && (<><H>{ru ? "Цвет узора" : "Pattern colour"}</H>{swatches("patternColor", COLORS)}</>)}
              <label className="fs-toggle"><input type="checkbox" checked={look.logo !== false} onChange={(e) => change({ logo: e.target.checked })} />
                <span>{ru ? "Надпись «Фоксинбург»" : "“Фоксинбург” logo"}</span></label>
            </>
          )}
          {cat === "bottom" && (<><H>{ru ? "Шорты" : "Shorts"}</H>{swatches("bottom", COLORS)}<H>{ru ? "Кеды" : "Sneakers"}</H>{swatches("shoes", COLORS, "walk")}</>)}
          {cat === "extras" && (
            <>
              <H>{ru ? "На шее" : "Neck"}</H>{chips("neck", NECK, "cheer")}
              <H>{ru ? "За спиной" : "Back"}</H>{chips("back", BACK, "jump")}
              {(look.neck !== "none" || look.back !== "none") && (<><H>{ru ? "Цвет аксессуаров" : "Accessory colour"}</H>{swatches("neckColor", COLORS)}</>)}
              <H><Backpack size={15} /> {ru ? "Рюкзак" : "Backpack"}</H>{swatches("bag", COLORS)}
            </>
          )}
          {cat === "scene" && (<><H>{ru ? "Где стоит Фокси" : "Scene"}</H>{chips("scene", SCENES, "wave")}</>)}
        </div>

        <div className="fs-actions">
          <button type="button" className="fs-btn fs-btn-go" onClick={save} disabled={saved === "saving"}>
            <Save size={18} />{saved === "ok" ? (ru ? "Сохранено!" : "Saved!") : ru ? "Сохранить Фокси" : "Save Foxi"}
          </button>
          <button type="button" className="fs-btn" onClick={random}><Shuffle size={18} />{ru ? "Случайно" : "Random"}</button>
          <button type="button" className="fs-btn" onClick={undo} disabled={!history.current.length}><Undo2 size={18} />{ru ? "Назад" : "Undo"}</button>
          <button type="button" className="fs-btn" onClick={() => change({ ...BASE, name: look.name })}><Scissors size={18} />{ru ? "Как в Фоксинбурге" : "Classic"}</button>
          <button type="button" className="fs-btn" onClick={photo} disabled={state !== "ready"}><Download size={18} />{ru ? "Фото" : "Photo"}</button>
        </div>
        {saved === "err" && <p className="k-err" role="alert">{ru ? "Не получилось сохранить. Попробуйте ещё раз." : "Could not save. Try again."}</p>}
      </aside>
    </div>
  );
}
