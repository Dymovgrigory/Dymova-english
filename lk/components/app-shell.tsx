"use client";

// Каркас кабинета: боковое меню (компьютер) / нижняя панель (телефон),
// верхняя строка с монетами Фоксинбурга, званием и выбором ребёнка.
import { usePathname } from "next/navigation";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";
import { BookOpenText, CalendarDays, Castle, Coins, House, Library, PawPrint, Shield } from "lucide-react";

const NAV = [
  { href: "/dashboard", ru: "Главная", en: "Home", Icon: House },
  { href: "/words", ru: "Слова", en: "Words", Icon: BookOpenText },
  { href: "/words/my", ru: "Мой словарь", en: "My words", Icon: Library },
  { href: "/foxi", ru: "Мой Фокси", en: "My Foxi", Icon: PawPrint },
  { href: "/schedule", ru: "Расписание", en: "Schedule", Icon: CalendarDays },
  { href: "/world", ru: "Мир", en: "World", Icon: Castle },
];

const isOn = (path: string, href: string) =>
  path === href || (path.startsWith(href + "/") && !(href === "/words" && path.startsWith("/words/my")));

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname() || "";
  const { lang } = useI18n();
  const { me, active, setActiveId, stats, logout } = useCabinet();
  const wallet = stats?.wallet ?? 0;
  const rank = stats?.rank;

  return (
    <div className="k-app">
      <aside className="k-side" aria-label={lang === "ru" ? "Разделы" : "Sections"}>
        <a className="k-logo" href="/dashboard">
          <img src="/foxi/guide.webp" alt="" width={44} height={72} />
          <span>Фоксинбург</span>
        </a>
        <nav className="k-nav">
          {NAV.map(({ href, ru, en, Icon }) => {
            const on = isOn(path, href);
            return (
              <a key={href} href={href} className={"k-nav-item" + (on ? " is-on" : "")} aria-current={on ? "page" : undefined}>
                <Icon size={24} strokeWidth={2.4} />
                <span>{lang === "ru" ? ru : en}</span>
              </a>
            );
          })}
        </nav>
        <div className="k-side-foot">
          <LangSwitch />
          <a className="k-link" href="/account">{lang === "ru" ? "Пароль для входа" : "Password"}</a>
          <button className="k-link" type="button" onClick={() => void logout()}>
            {lang === "ru" ? "Выйти" : "Log out"}
          </button>
        </div>
      </aside>

      <div className="k-main">
        <header className="k-top">
          {me && me.profiles.length > 1 ? (
            <div className="k-kids" role="tablist" aria-label={lang === "ru" ? "Ребёнок" : "Child"}>
              {me.profiles.map((p) => (
                <button key={p.id} role="tab" aria-selected={p.id === active?.id}
                  className={"k-kid" + (p.id === active?.id ? " is-on" : "")} onClick={() => setActiveId(p.id)}>
                  <span className="k-kid-ava">{(p.child_name || "?").slice(0, 1)}</span>
                  {p.child_name}
                </button>
              ))}
            </div>
          ) : (
            <div className="k-hello">{active?.child_name || me?.account.parent_name || ""}</div>
          )}
          <div className="k-top-stats">
            {rank && (
              <span className="k-chip k-chip-rank" title={lang === "ru" ? "Звание жителя Фоксинбурга" : "Foxinburg rank"}>
                <Shield size={18} strokeWidth={2.6} /> <span className="k-chip-label">{rank.title}</span>
              </span>
            )}
            <a className="k-chip k-chip-coin" href="/world" title={lang === "ru" ? "Монеты Фоксинбурга — трать в Мире" : "Foxinburg coins — spend them in the World"}>
              <Coins size={20} strokeWidth={2.6} /> {wallet}
            </a>
          </div>
        </header>
        <main className="k-content">{children}</main>
      </div>

      <nav className="k-tabbar" aria-label={lang === "ru" ? "Разделы" : "Sections"}>
        {NAV.map(({ href, ru, en, Icon }) => {
          const on = isOn(path, href);
          return (
            <a key={href} href={href} className={"k-tab" + (on ? " is-on" : "")} aria-current={on ? "page" : undefined}>
              <Icon size={24} strokeWidth={2.4} />
              <span>{lang === "ru" ? ru : en}</span>
            </a>
          );
        })}
      </nav>
    </div>
  );
}
