import type { NextConfig } from "next";

const WORLD_API = process.env.WORLD_API || "http://127.0.0.1:8010";

const config: NextConfig = {
  // Docker: компактный runtime-образ (см. lk/Dockerfile).
  output: "standalone",
  // Локальная разработка: открываем и через 127.0.0.1 (Kimi Work превью, e2e).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // ЛК разворачивается на поддомене lms.dymova-english.ru; закрытая зона —
  // от индексации (ТЗ §9). Маркетинговый сайт живёт отдельно на основном домене.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/lk/:path*",
        destination: `${WORLD_API}/api/lk/:path*`,
      },
      // Админка школы (вход сотрудника, пароли родителей для ЛК)
      {
        source: "/api/v2/admin/:path*",
        destination: `${WORLD_API}/api/v2/admin/:path*`,
      },
    ];
  },
};

export default config;
