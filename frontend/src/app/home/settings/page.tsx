import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SettingsForm } from "@/components/settings-form";

type FamilySettings = { base_currency: string };

export default async function SettingsPage() {
  const session = await requireSession();
  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Settings" backHref="/home" />
      <SettingsForm currentCurrency={settings.base_currency} />
    </div>
  );
}
