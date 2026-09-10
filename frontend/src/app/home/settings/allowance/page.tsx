import { PageHeader } from "@/components/ui/page-header";
import { AllowanceSettingsForm } from "@/components/allowance-settings-form";

export default function AllowanceSettingsPage() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Allowance" backHref="/home/settings" />
      <AllowanceSettingsForm />
    </div>
  );
}
