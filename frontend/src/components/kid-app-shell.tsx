"use client";

import type { ReactNode } from "react";
import { KidFamilyProvider } from "@/lib/kid-family-store";
import type { KidMe } from "@/lib/types";

/** Client boundary for the kid app's authenticated area — hands the
 * session token and the resolved `/kid/me` identity to KidFamilyProvider,
 * which seeds the shared `useFamily()` store. */
export function KidAppShell({
  token,
  identity,
  children,
}: {
  token: string;
  identity: KidMe;
  children: ReactNode;
}) {
  return (
    <KidFamilyProvider identity={identity} token={token}>
      {children}
    </KidFamilyProvider>
  );
}
