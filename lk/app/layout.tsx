import type { Metadata, Viewport } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "Личный кабинет — Фоксинбург",
  description:
    "Личный кабинет школы Фоксинбург: расписание, прогресс, тренажёр слов и Мир Фоксинбурга.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Providers>
          <div className="shell">{children}</div>
        </Providers>
      </body>
    </html>
  );
}
