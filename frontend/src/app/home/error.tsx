"use client";

import { ErrorState } from "@/components/ui/error-state";

export default function HomeError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return <ErrorState error={error} retry={retry} homeHref="/home" />;
}
