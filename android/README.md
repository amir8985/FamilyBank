# FamilyBank on Google Play — runbook

This wraps the existing web app (`family-bank-nine.vercel.app`) as a
Trusted Web Activity (TWA) — no separate native codebase, no rewrite.
The site itself doesn't change; this just makes it installable from
Google Play as a full-screen Android app.

**Environment note:** this repo has no local Java/Android SDK, so
everything that needs to actually compile Android code runs in GitHub
Actions instead (`.github/workflows/android-*.yml`), which has that
tooling preinstalled. Nothing here needs you to install Android Studio.

## One-time setup (do this once, in order)

1. **Add a bootstrap secret.** In GitHub → repo Settings → Secrets and
   variables → Actions, add `KEYSTORE_BOOTSTRAP_PASSWORD` — any strong
   password you choose, used to protect the signing key you're about to
   generate. Write it down somewhere safe (a password manager) — you'll
   need it again in step 3.

2. **Run "Android - Generate signing keystore" once**, from the Actions
   tab (workflow_dispatch — click "Run workflow"). This is the *only*
   time this should ever run: it creates the one signing key every
   future update to this app must be signed with. Re-running it later
   would create a different key and orphan this one — Play Store
   requires the same signing identity across all updates to a listing.
   - Download the `android-release-keystore` artifact from the
     finished run (a `.keystore` file).
   - Open the run's log and copy the `SHA256:` fingerprint it printed.

3. **Turn the keystore into two more secrets:**
   - `ANDROID_KEYSTORE_PASSWORD` — the same password from step 1.
   - `ANDROID_KEYSTORE_BASE64` — base64 of the downloaded `.keystore`
     file. On your machine: `certutil -encode android-release.keystore
     tmp.b64` (Windows) or `base64 -i android-release.keystore` (Mac/
     Linux), then paste the result (strip the `-----BEGIN...-----`
     header/footer lines if using `certutil`) as the secret value.
   - Keep the downloaded `.keystore` file itself somewhere safe outside
     git too, as a backup — if these secrets are ever lost, so is the
     ability to publish an update to this listing.

4. **Fill in the real fingerprint.** Edit
   `frontend/public/.well-known/assetlinks.json`, replacing
   `REPLACE_ME_WITH_SHA256_FROM_GENERATE_KEYSTORE_WORKFLOW` with the
   fingerprint from step 2 (keep the colons, it goes in as printed).
   Commit, merge to `master` — this deploys automatically. This file is
   what lets the Android app open full-screen (no Chrome address bar)
   instead of falling back to an ordinary browser tab; wrong or missing,
   the app still works, it just won't look fully "native."

5. **Run "Android - Build signed .aab"** from the Actions tab. Download
   the `familybank-release` artifact when it finishes — that `.aab` file
   is what you upload to Play Console. See the workflow file's own
   comments if this step needs adjusting on the first run — Bubblewrap's
   scaffolding step (`bubblewrap init`) couldn't be dry-run in this
   environment (no local JDK), so treat the first CI run as something to
   watch rather than assume works blind.

## Play Console (your own account — I can't do this part)

1. Create a developer account at [play.google.com/console](https://play.google.com/console)
   — $25 one-time fee, your own identity/payment.
2. Create a new app → upload the `.aab` from step 5 above to the
   Internal Testing track first (lets you install and check it actually
   works before it's public).
3. **You almost certainly do NOT need to opt into "Designed for
   Families."** That program is for apps *primarily used by children
   under 13 as the end user*. FamilyBank's actual signed-in user is
   always a parent (kids never touch Google sign-in) — list it as a
   normal Finance/Education/Parenting app instead. Opting into Families
   adds real extra restrictions (ads policy, stricter data rules) this
   app doesn't need.
4. Fill in the store listing — draft copy below.
5. Fill in the "Data safety" form — draft answers below, matching
   `/privacy` exactly (keep them in sync if you edit one).
6. Content rating questionnaire — answer honestly; nothing in the app
   (violence, gambling-style mechanics, user-generated content) should
   trigger anything above the lowest rating tier, but Google's
   questionnaire is the actual source of truth, not this note.
7. Once Internal Testing looks right, promote to Production.

## Store listing — draft copy

**App name:** FamilyBank

**Short description** (≤80 chars):
> Track allowance you owe your kids — they invest it at real prices.

**Full description:**
> FamilyBank is a virtual allowance tracker with a real-market lesson
> built in. Track the allowance or debt you owe each of your kids, and
> let them "invest" that balance in real stocks and index funds at
> real, live market prices.
>
> No real broker, no real trades, no real money ever moves — every
> price your kid sees is real, but every dollar behind it is play money.
> It's a family ledger with an investing lesson, not a brokerage
> account.
>
> • Track allowance and chores paid, per kid, with full history
> • Kids browse and "buy" real stocks/index funds at live prices
> • Since-purchase performance, just like a real portfolio
> • Only a parent can add money — everything else is safe to hand over
> • Multi-currency support
>
> Sign in with Google to get started.

## Data safety form — draft answers

Matches `/privacy`. If you ever change what the app collects, update
both.

- **Does your app collect or share any required user data?** Yes.
- **Data collected:** Name, email address (via Google Sign-In).
  App-specific data you enter yourself (kids' names, balances,
  transaction history) — this is user-generated content the parent
  enters, not collected *from* a third party or device.
- **Is data encrypted in transit?** Yes (HTTPS throughout).
- **Can users request data deletion?** Yes — via emailing the contact
  address in `/privacy`.
- **Is data shared with third parties?** No data is sold or shared for
  advertising/marketing. Processing is limited to the service providers
  disclosed in `/privacy` (Google for auth, Neon/Vercel/Render for
  hosting, a market-data provider for prices — none of which receive
  personal data beyond what's needed to run the service).
- **Financial info collected?** No real financial info (bank/card
  numbers) is ever collected — there's nothing to charge.
- **Target audience / “Families” eligibility:** Adults (parents) — see
  the "Designed for Families" note above.
