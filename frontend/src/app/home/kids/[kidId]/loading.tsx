import { Skeleton } from "@/components/ui/skeleton";

export default function PortfolioLoading() {
  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen px-5">
      <div className="pt-6 pb-4 flex items-center gap-3">
        <Skeleton className="w-9 h-9 rounded-full shrink-0" />
        <Skeleton className="h-5 w-28" />
      </div>
      <div className="bg-card rounded-2xl p-4 border border-border-hairline shadow-[0_1px_3px_rgba(0,0,0,.06)] flex flex-col gap-2.5 mb-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-36" />
      </div>
      <div className="flex flex-col gap-2.5">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    </div>
  );
}
