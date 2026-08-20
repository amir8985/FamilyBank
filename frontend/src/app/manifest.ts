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
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
