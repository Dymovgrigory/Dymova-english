import type { Metadata } from "next";
import { Montserrat, Nunito, Playfair_Display } from "next/font/google";
import { AppGate } from "@/features/gate/AppGate";
import "./globals.css";

const montserrat = Montserrat({
  variable: "--font-display",
  subsets: ["cyrillic", "latin"],
  weight: ["600", "700", "800"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["cyrillic", "latin"],
  weight: ["700", "800", "900"],
});

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["cyrillic", "latin"],
  weight: ["400", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Фоксинбург — тренажёр английского по Spotlight",
  description:
    "Короткие уроки по учебнику Spotlight: слова, чтение, грамматика и говорение. Замок Фоксинбурга — награда за учёбу.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ru"
      className={`${montserrat.variable} ${playfair.variable} ${nunito.variable} ${nunito.className} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <AppGate>{children}</AppGate>
      </body>
    </html>
  );
}
