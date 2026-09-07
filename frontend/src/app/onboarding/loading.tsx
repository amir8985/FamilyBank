import { Skeleton } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";

export default function OnboardingLoading() {
  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col px-5 pt-[58px]">
      <Logo />
      <div className="flex-1 flex flex-col justify-center gap-4">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-11 w-32 mt-2" />
      </div>
    </div>
  );
}
