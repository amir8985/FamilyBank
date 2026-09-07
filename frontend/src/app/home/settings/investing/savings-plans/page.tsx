import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SavingsPlansForm } from "@/components/savings-plans-form";
import type { SavingsPlanOut } from "@/lib/types";

export default async function SavingsPlansSettingsPage() {
  const session = await requireSession();
  const plans = await api.get<SavingsPlanOut[]>("/family/savings-plans", session.backendToken);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      {/* Skips the hub, straight back to Settings — same call as the
          boost page (the hub isn't worth stopping at). */}
      <PageHeader title="Savings plans" backHref="/home/settings" />
      <SavingsPlansForm initialPlans={plans} />
    </div>
  );
}
