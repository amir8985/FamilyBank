import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { BoostSettingsForm } from "@/components/boost-settings-form";
import type { FamilySettings } from "@/lib/types";

export default async function BoostSettingsPage() {
  const session = await requireSession();
  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      {/* Back skips the one-card hub and goes straight to Settings —
          the hub adds nothing to return through, and the user asked for
          a faster way out of this screen specifically. */}
      <PageHeader title="Stock boost" backHref="/home/settings" />
      <BoostSettingsForm currentRate={settings.boost_buffer_rate} />
    </div>
  );
}
