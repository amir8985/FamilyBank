import { Skeleton } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";

export default function HomeLoading() {
  return (
    <div className="max-w-md mx-auto flex flex-col min-h-screen">
      <div className="pt-[58px] px-5 pb-2 flex items-center justify-between">
        <Logo />
        <div className="w-8 h-8 rounded-full bg-tint-icon" />
      </div>

      <div className="px-5 pt-4 pb-1.5">
        <div className="bg-card rounded-2xl p-4 border border-border-hairline shadow-[0_1px_3px_rgba(0,0,0,.06)] flex flex-col gap-2.5">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-9 w-40" />
        </div>
      </div>

      <div className="flex-1 px-5 pt-3.5 pb-6 flex flex-col gap-3">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="bg-card rounded-2xl p-4 border border-border-hairline shadow-[0_1px_3px_rgba(0,0,0,.06)] flex items-center gap-3"
          >
            <Skeleton className="w-11 h-11 rounded-full shrink-0" />
            <div className="flex-1 flex flex-col gap-2">
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-5 w-32" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
