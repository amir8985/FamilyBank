"use client";

import { use } from "react";
import { useSearchParams } from "next/navigation";
import { KidPortfolioScreen } from "@/components/kid-portfolio-screen";

export default function KidPortfolioPage({
  params,
}: {
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = use(params);
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") === "buy" ? "buy" : "holdings";
  return <KidPortfolioScreen kidId={kidId} initialTab={initialTab} />;
}
