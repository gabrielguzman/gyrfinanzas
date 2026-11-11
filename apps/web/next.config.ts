import type { NextConfig } from "next";

// La web llama a /api/... y Next lo reenvía a la API. Así todo sale del mismo
// origen: sin CORS y funciona igual desde la compu o desde el celu.
const API_URL = process.env.API_URL || `http://127.0.0.1:${process.env.API_PORT || 8000}`;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // En la imagen de Docker se compila «standalone» (servidor mínimo, sin node_modules completos).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // La demo usa otra carpeta de compilación para poder correr junto a la app real.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
