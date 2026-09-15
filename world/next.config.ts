import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/api/world/:path*",
        destination: "http://127.0.0.1:8010/api/world/:path*",
      },
    ];
  },
};

export default nextConfig;
