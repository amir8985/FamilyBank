import { redirect } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import type { FamilySettings } from "@/lib/types";

export default async function HomeLayout({ children }: LayoutProps<"/home">) {
  const session = await requireSession();

  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);
  if (!settings.onboarding_completed) redirect("/onboarding");

  return <div className="min-h-screen bg-cream">{children}</div>;
}
