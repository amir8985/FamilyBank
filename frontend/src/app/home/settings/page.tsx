import { PageHeader } from "@/components/ui/page-header";
import { SettingsForm } from "@/components/settings-form";
import packageJson from "../../../../package.json";

// Everything this screen needs — the family currency and the kid list —
// is already in the client family store from `/home`. No server round-trip
// on navigation here (it used to make two: `/family/settings` + `/home`,
// the first fully redundant with the second).
export default function SettingsPage() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Settings" backHref="/home" />
      <SettingsForm />
      <div className="text-center text-[12px] text-muted pb-6">v{packageJson.version}</div>
    </div>
  );
}
