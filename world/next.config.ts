import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    // Dev-прокси на локальный API. В проде клиент ходит на NEXT_PUBLIC_WORLD_API.
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/world/:path*",
        destination: "http://127.0.0.1:8010/api/world/:path*",
      },
    ];
  },
};

export default nextConfig;
