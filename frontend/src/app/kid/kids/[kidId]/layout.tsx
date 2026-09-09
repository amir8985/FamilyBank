import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getKidToken } from "@/lib/kid-session";
import { KidAppShell } from "@/components/kid-app-shell";
import type { KidMe } from "@/lib/types";

// Auth guard for one kid's area. The cookie is per-kid (`kid_sess_<id>`)
// so siblings sharing a device stay independent.
//
// Unlike the parent app's home/layout.tsx (which must NOT await its heavy
// `/home` fetch), `/kid/me` is a single fast query that EVERY route below
// needs, and there's nothing to render before we know who this is — so
// awaiting here is right, and it lets us catch a revoked/expired session
// (401/403) and show the calm "ask a parent for a link" screen instead
// of a scary error boundary. (A server→client promise rejection loses
// the ApiError type, so the check has to happen here, server-side.)
export default async function KidLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ kidId: string }>;
}) {
  const { kidId } = await params; // the kid's opaque public_id
  const token = await getKidToken(kidId);
  if (!token) redirect("/kid/locked");

  let identity: KidMe;
  try {
    identity = await api.get<KidMe>("/kid/me", token);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
      redirect("/kid/locked?revoked=1");
    }
    throw err;
  }
  // Cookie/URL mismatch (shouldn't normally happen) — send them to their own.
  if (identity.public_id !== kidId) redirect(`/kid/kids/${identity.public_id}`);

  return (
    <div className="min-h-screen bg-cream">
      <KidAppShell token={token} identity={identity}>
        {children}
      </KidAppShell>
    </div>
  );
}
