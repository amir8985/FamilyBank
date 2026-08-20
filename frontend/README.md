# FamilyBank (frontend)

Next.js 16 (App Router, TypeScript, Tailwind v4) implementing the four
core screens + marketing landing page from `../design_handoff_familybank/`,
wired to the FastAPI backend in `../backend/`.

## Setup

```bash
npm install
cp .env.local.example .env.local   # fill in Google OAuth + AUTH_SECRET
npm run dev
```

Visit `http://localhost:3000`. The backend must be running (see
`../backend/README.md`) for anything past the landing page — sign-in
calls `POST {BACKEND_URL}/auth/sync`, and every authenticated page
fetches from it directly.

### Google OAuth

1. Google Cloud Console → APIs & Services → Credentials → Create OAuth
   client ID → Web application.
2. Authorized redirect URI: `http://localhost:3000/api/auth/callback/google`
   (add your production domain's equivalent later).
3. Put the client ID/secret in `.env.local` as `AUTH_GOOGLE_ID` /
   `AUTH_GOOGLE_SECRET`. The same client ID also goes in the backend's
   `.env` as `GOOGLE_CLIENT_ID` (used only to verify token audience).

Google is the only sign-in method — no email/password, by design.

## Layout

```
src/
  auth.ts              NextAuth (Google-only) config + backend session sync
  lib/
    api.ts              typed fetch helpers (server + client) against the backend
    session.ts           requireSession() — server-side auth guard
    types.ts              mirrors backend/app/schemas/*.py
    format.ts              currency/percent/units formatting
  components/            shared UI (bottom sheet, segmented control, avatar...)
                          and per-screen client components (home, portfolio, buy, sheets)
  app/
    page.tsx              marketing landing page (public)
    home/                  parent home, kid portfolio, buy flow, settings (all authed)
```

## Auth flow

1. `SignInButton` calls `signIn("google")`.
2. On first callback, `auth.ts`'s `jwt` callback POSTs Google's own
   `id_token` to the backend's `/auth/sync`, which verifies it directly
   against Google, finds-or-creates the family, and returns a
   backend-issued session token.
3. That token is stashed in the NextAuth session (`session.backendToken`)
   and sent as `Authorization: Bearer ...` on every backend call — see
   `lib/api.ts` and `lib/session.ts`.

## PWA

`app/manifest.ts` + `public/sw.js` (a no-op pass-through worker) make
"Add to Home Screen" installable — not offline trading, just
installability, per the architecture doc.
