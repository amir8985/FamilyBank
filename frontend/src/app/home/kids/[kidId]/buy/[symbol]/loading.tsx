import { Skeleton } from "@/components/ui/skeleton";

export default function BuyLoading() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col px-5">
      <div className="pt-6 pb-4 flex items-center gap-3">
        <Skeleton className="w-9 h-9 rounded-full shrink-0" />
        <Skeleton className="h-5 w-24" />
      </div>
      <Skeleton className="h-32 w-full mb-4" />
      <Skeleton className="h-14 w-full mb-3" />
      <Skeleton className="h-11 w-full" />
    </div>
  );
}
