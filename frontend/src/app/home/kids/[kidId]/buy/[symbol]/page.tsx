"use client";

import { use } from "react";
import { useSearchParams } from "next/navigation";
import { BuyScreen } from "@/components/buy-screen";

export default function BuyPage({
  params,
}: {
  params: Promise<{ kidId: string; symbol: string }>;
}) {
  const { kidId, symbol } = use(params);
  const searchParams = useSearchParams();
  const from = searchParams.get("from") === "buy" ? "buy" : "holdings";
  return <BuyScreen kidId={kidId} symbol={symbol} backTab={from} />;
}
