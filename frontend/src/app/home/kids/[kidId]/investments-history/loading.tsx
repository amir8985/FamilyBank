import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";

export default function InvestmentHistoryLoading() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <PageHeader title="Investments" backHref="/home" />
      <div className="px-5 pt-3 flex flex-col gap-2.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    </div>
  );
}
