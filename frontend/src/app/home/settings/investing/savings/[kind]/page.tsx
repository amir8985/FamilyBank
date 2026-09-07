import { notFound } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/page-header";
import { SavingsKindForm } from "@/components/savings-kind-form";
import type { SavingsPlanOut, SavingsPresetOut } from "@/lib/types";

export default async function SavingsKindSettingsPage({
  params,
}: {
  params: Promise<{ kind: string }>;
}) {
  const { kind } = await params;
  if (kind !== "flexible" && kind !== "locked") notFound();

  const session = await requireSession();
  const [plans, presets] = await Promise.all([
    api.get<SavingsPlanOut[]>("/family/savings-plans", session.backendToken),
    api.get<SavingsPresetOut[]>("/family/savings-presets", session.backendToken),
  ]);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader
        title={kind === "flexible" ? "Flexible savings" : "Locked savings"}
        backHref="/home/settings/investing"
      />
      <SavingsKindForm kind={kind} plans={plans} presets={presets} />
    </div>
  );
}
