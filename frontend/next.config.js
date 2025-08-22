/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.NODE_ENV === "development"
            ? "http://localhost:8000/:path*" // Local FastAPI during dev
            : "https://my-nutrition-bot-backend.onrender.com/:path*", // Deployed backend
      },
    ];
  },
};

module.exports = nextConfig;

