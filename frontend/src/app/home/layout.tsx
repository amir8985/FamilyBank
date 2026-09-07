import { Suspense } from "react";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import { FamilyProvider } from "@/lib/family-store";
import type { FamilyHome, FamilySettings } from "@/lib/types";

// Next.js: a layout that does an uncached *fetch* blocks navigation for
// every route beneath it, and none of that segment's loading.tsx files
// can show for it (loading.tsx only wraps page.js + nested layouts, never
// the segment's own layout.js — see
// node_modules/next/dist/docs/.../file-conventions/layout.md,
// "Interaction with loading.js"; AGENTS.md warns this Next version's
// conventions differ from training data, and this is a concrete example).
//
// So the two things this layout needs are handled separately:
//
//  1. Auth guard — `requireSession()` only reads/verifies the session
//     cookie (no network), so awaiting it here is a sub-millisecond
//     block, and it's the single place that now guards the whole segment
//     since the pages below are Client Components that can't call it
//     themselves.
//
//  2. The `/home` seed + the onboarding-completed check — both real
//     backend calls, so both stay inside their own Suspense boundaries.
//     `OnboardingGate` renders nothing on the happy path; `FamilyProvider`
//     shows a skeleton until the seed resolves (once per session — every
//     navigation after that reads the client store instantly).
//
// Trade-off, unchanged from before: a user who lands on a /home/* URL
// before finishing onboarding may see a flash of real content before the
// redirect fires. Not a security issue — the backend enforces real
// authorization on every call regardless.

async function OnboardingGate() {
  const session = await requireSession();
  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);
  if (!settings.onboarding_completed) redirect("/onboarding");
  return null;
}

export default async function HomeLayout({ children }: LayoutProps<"/home">) {
  const session = await requireSession();
  // Started here, NOT awaited — streams to FamilyProvider, which reads it
  // with React's `use()` inside its own Suspense boundary.
  const homePromise = api.get<FamilyHome>("/home", session.backendToken);

  return (
    <div className="min-h-screen bg-cream">
      <Suspense fallback={null}>
        <OnboardingGate />
      </Suspense>
      <FamilyProvider homePromise={homePromise}>{children}</FamilyProvider>
    </div>
  );
}
