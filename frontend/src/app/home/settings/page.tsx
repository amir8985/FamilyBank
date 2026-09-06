import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsForm } from "@/components/settings-form";
import type { FamilyHome, FamilySettings } from "@/lib/types";
import packageJson from "../../../../package.json";

export default async function SettingsPage() {
  const session = await requireSession();
  const [settings, home] = await Promise.all([
    api.get<FamilySettings>("/family/settings", session.backendToken),
    api.get<FamilyHome>("/home", session.backendToken),
  ]);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Settings" backHref="/home" />
      <SettingsForm currentCurrency={settings.base_currency} kids={home.kids} />
      <div className="text-center text-[12px] text-muted pb-6">v{packageJson.version}</div>
    </div>
  );
}
