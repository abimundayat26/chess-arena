import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  agentRules: false,
  output: "standalone",
  async rewrites() {
    return [{
      source: "/api/:path*",
      destination: `${process.env.CHESS_API_URL ?? "http://127.0.0.1:8000"}/:path*`,
    }]
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ]
  },
}

export default nextConfig
