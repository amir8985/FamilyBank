import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";

export default function AllowanceLoading() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Allowance" backHref="/home/settings" />
      <div className="px-5 pt-4 flex flex-col gap-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
    </div>
  );
}
