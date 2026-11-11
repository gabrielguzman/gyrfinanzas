import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "gyrfinanzas",
    short_name: "gyrfinanzas",
    description: "Tus finanzas: cargá en segundos, entendé todo.",
    start_url: "/",
    display: "standalone",
    background_color: "#F4F3EE",
    theme_color: "#F4F3EE",
    lang: "es-AR",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [{ name: "Cargar algo", url: "/?cargar=1" }],
  };
}
