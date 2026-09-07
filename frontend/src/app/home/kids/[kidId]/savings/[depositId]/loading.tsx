import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col">
      <div className="pt-6 px-5 pb-1 flex items-center gap-2.5">
        <Skeleton className="w-[26px] h-[26px] rounded-full" />
        <Skeleton className="h-6 w-40" />
      </div>
      <div className="px-5 pt-4 flex flex-col gap-4">
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-11 rounded-xl" />
      </div>
    </div>
  );
}
