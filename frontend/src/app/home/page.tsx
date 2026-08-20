import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { HomeClient } from "@/components/home-client";
import type { FamilyHome } from "@/lib/types";

export default async function HomePage() {
  const session = await requireSession();
  const home = await api.get<FamilyHome>("/home", session.backendToken);
  return <HomeClient home={home} />;
}
