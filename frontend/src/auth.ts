import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  session: { strategy: "jwt" },
  trustHost: true,
  callbacks: {
    async jwt({ token, account }) {
      // Only runs on initial sign-in, when Google's own id_token is
      // available — this is what proves identity to the backend, not
      // anything NextAuth invents itself (see backend/app/api/routes_auth.py).
      if (account?.id_token) {
        try {
          const res = await fetch(`${BACKEND_URL}/auth/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: account.id_token }),
          });
          if (res.ok) {
            const data = await res.json();
            token.backendToken = data.session_token;
            token.familyId = data.family_id;
            token.baseCurrency = data.base_currency;
          }
        } catch {
          // Backend unreachable — session still gets created, but
          // protected pages will redirect until the sync succeeds.
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.backendToken = token.backendToken as string | undefined;
      session.familyId = token.familyId as string | undefined;
      session.baseCurrency = token.baseCurrency as string | undefined;
      return session;
    },
  },
});
