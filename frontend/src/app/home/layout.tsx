import { Suspense } from "react";
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/session";
import { api } from "@/lib/api";
import type { FamilySettings } from "@/lib/types";

// Next.js: a layout that reads cookies()/does an uncached fetch blocks
// navigation for *every* route beneath it — none of the loading.tsx
// files under /home would ever show, because loading.tsx can't cover a
// segment's own layout, only the page.js (and nested layouts) below it.
// See node_modules/next/dist/docs/.../file-conventions/layout.md,
// "Interaction with loading.js". Wrapping the redirect-gate's own fetch
// in its own Suspense boundary (fallback=null — it renders nothing on
// the happy path) unblocks that: `children` streams in immediately
// under its own per-route loading.tsx, while this gate resolves
// independently and still redirects the moment it knows onboarding
// isn't done.
//
// Trade-off, accepted deliberately: this means a user who somehow lands
// on a /home/* URL before completing onboarding could see a flash of
// that page's real content for a moment before the redirect fires,
// instead of never seeing it. Not a security issue (the backend still
// enforces real authorization on every API call regardless of what this
// gate does) — just a very rare, purely cosmetic edge case, traded for
// instant navigation on every normal request.
async function OnboardingGate() {
  const session = await requireSession();
  const settings = await api.get<FamilySettings>("/family/settings", session.backendToken);
  if (!settings.onboarding_completed) redirect("/onboarding");
  return null;
}

export default function HomeLayout({ children }: LayoutProps<"/home">) {
  return (
    <div className="min-h-screen bg-cream">
      <Suspense fallback={null}>
        <OnboardingGate />
      </Suspense>
      {children}
    </div>
  );
}
