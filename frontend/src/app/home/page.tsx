import { HomeClient } from "@/components/home-client";

// Data comes from the client family store (seeded once in home/layout.tsx),
// so this navigation is instant — no per-visit server round-trip. The
// auth guard lives in the layout.
export default function HomePage() {
  return <HomeClient />;
}
