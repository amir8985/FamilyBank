import { redirect } from "next/navigation";
import { auth } from "@/auth";

/** Server-only. Redirects to the landing page unless a synced backend
 * session exists (see auth.ts's jwt callback / backend /auth/sync). */
export async function requireSession() {
  const session = await auth();
  if (!session?.backendToken || !session.familyId || !session.baseCurrency) {
    redirect("/");
  }
  return session as typeof session & {
    backendToken: string;
    familyId: string;
    baseCurrency: string;
  };
}
