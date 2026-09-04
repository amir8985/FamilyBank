import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "FamilyBank",
    short_name: "FamilyBank",
    description:
      "Track the allowance you owe your kids, and let them invest it in real stocks and indices.",
    start_url: "/home",
    display: "standalone",
    background_color: "#f7f6f2",
    theme_color: "#1b3a30",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Full-bleed, safe-zone-padded variant — Android's adaptive icon
      // mask crops right up to the edge, so a maskable icon needs its
      // content well inside the crop line (see icon-maskable.svg).
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
