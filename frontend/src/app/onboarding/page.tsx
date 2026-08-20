import { redirect } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { OnboardingClient } from "@/components/onboarding-client";
import type { FamilySettings } from "@/lib/types";

export default async function OnboardingPage() {
  const session = await requireSession();
  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);

  if (settings.onboarding_completed) redirect("/home");

  return <OnboardingClient />;
}
