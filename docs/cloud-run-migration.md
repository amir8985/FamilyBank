# Backend migration: Render → Cloud Run (Frankfurt)

Status: **DONE (2026-09-11).** Production backend is on Cloud Run, cutover
verified against real traffic, auto-deploy working, cron confirmed healthy
over a full day, daily backups green. Kept as a reference for the exact
commands and the decisions behind them — see `CLAUDE.md`'s "Backend
migrated Render → Cloud Run" entry for the current-state summary.
Remaining: Render is intentionally still running as a standby (delete
later, no rush — see Part 8); the monitoring alert in Part 7 was removed
as unreliable, not replaced.

## Why

1. **Latency.** Render's instance and the Neon database are in different
   regions, so every DB round-trip pays ~300–450 ms regardless of query
   cost. Cloud Run in `europe-west3` (Frankfurt) sits next to Neon
   (also Frankfurt) → round-trips drop to single-digit ms. This is the
   real fix for the production slowness; nothing else substitutes for it.
2. **Fit.** The app is I/O-bound and bursty — a scale-to-zero,
   request-priced platform suits it better than a always-on instance.
3. **Decoupling the scheduler.** The in-process refresh loop only works
   because exactly one instance is always alive. Moving the trigger to
   Cloud Scheduler removes that constraint (see "The refresh job" below).

## Decisions already made

| Question | Answer |
|---|---|
| Region | `europe-west3` (Frankfurt), matching Neon |
| Refresh trigger | **Cloud Scheduler → `POST /internal/refresh`** on the web service (option "2a"). Not a separate Cloud Run Job — reusing the existing endpoint means one code path, shared with the staleness fallback. The refresh is ~10 s of `await`ed HTTP; it doesn't meaningfully compete with request serving at this scale. |
| Auth for the trigger | Keep the `X-Scheduler-Secret` header check (`INTERNAL_SCHEDULER_SECRET`). The service must allow unauthenticated invocations anyway (users hit it), so Cloud Run IAM can't protect just that route. |
| Custom domain | No — the backend URL is only consumed by the Vercel frontend and Cloud Scheduler, never typed by a human. Use the `*.run.app` URL. |
| Cron schedule | `1 */3 * * *` **UTC** — one Cloud Scheduler job, every 3 h (8 runs/day), max gap 3 h. Even coverage across all timezones (a quiet hour in Frankfurt is market hours somewhere). Not market-time-aligned on purpose — the boost math is frequency-independent (see below) and other exchanges have other hours. |
| Migrations | Run once per deploy as a Cloud Build step, **not** in the Dockerfile (autoscaled containers would race) and not on startup. |
| Auto-deploy | Cloud Build trigger on push to `master` → `cloudbuild.yaml`. Same model as Render today. |

## What's in the repo already (branch `perf-followups`)

- **`backend/app/scheduler/jobs.py`**
  - `run_refresh()` now takes a Postgres **session-level advisory lock**
    (`_REFRESH_LOCK_KEY`) around the actual work (`_run_refresh()`). A
    second trigger while one is running logs and returns immediately —
    safe for cron-retry overlap, deploy-cutover overlap, or the fallback
    racing the cron. Prevents duplicate `price_ticks` rows (the one
    non-idempotent part of a refresh).
  - `spawn_refresh_if_stale(prices_as_of)` — the **staleness fallback**.
    Called from `/home` and `/catalog` with the timestamp they already
    loaded (zero extra queries on the fresh path). If prices are older
    than `REFRESH_STALENESS_THRESHOLD_HOURS` (default 10 h ≈ 3 missed
    3-hourly runs), it fires a best-effort background `run_refresh()`.
    Insurance for a missed cron run — not the primary mechanism.
  - `set_stale_fallback_enabled()` — test-only switch (off for the suite,
    like `request_logging.set_persist_enabled`).
- **`backend/app/core/config.py`** — new `refresh_staleness_threshold_hours`.
- **`backend/Dockerfile`**, **`backend/.dockerignore`** — the Cloud Run image.
- **`cloudbuild.yaml`** (repo root) — build → push → migrate → deploy.
- **`render.yaml`** — comment noting the Cloud Run plan; `SCHEDULER_ENABLED`
  stays `true` on Render until cutover.

---

## Part 0 — Prerequisites

- **GCP project: reuse the existing `familybank` project** (currently
  only used for the Google OAuth client). Keeping everything in one
  project is the point — the OAuth client, Cloud Run, secrets, and the
  scheduler all in one place. Note its **project ID** (console → project
  picker → the ID under the name, e.g. `familybank-xxxxxx`).
- Billing account linked to the project (required even for free-tier
  usage; you won't be charged at this volume, but Cloud Run/Build refuse
  to run without one).
- `gcloud` CLI installed and authed: `gcloud auth login`,
  `gcloud config set project <PROJECT_ID>`.

```bash
export PROJECT_ID=<your-project-id>
export REGION=europe-west3
gcloud config set project $PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

## Part 1 — Artifact Registry + Secrets

```bash
gcloud artifacts repositories create familybank \
  --repository-format=docker --location=$REGION

# One secret per value currently in Render's dashboard.
# DATABASE_URL must be the asyncpg form:
#   postgresql+asyncpg://USER:PASS@HOST/DB   (no ?sslmode / ?channel_binding)
printf '%s' 'postgresql+asyncpg://...frankfurt-neon-host.../familybank' \
  | gcloud secrets create DATABASE_URL --data-file=-
printf '%s' '<google oauth client id>'   | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
printf '%s' '<backend jwt secret>'       | gcloud secrets create BACKEND_JWT_SECRET --data-file=-
printf '%s' '<internal scheduler secret>'| gcloud secrets create INTERNAL_SCHEDULER_SECRET --data-file=-
printf '%s' 'https://family-bank-nine.vercel.app,https://<any other origin>' \
  | gcloud secrets create CORS_ORIGINS --data-file=-
```

> **Neon:** if the current Neon project is not in Frankfurt, create a new
> Neon project (or branch) in the Frankfurt region and point
> `DATABASE_URL` at it. Migrations (Part 3) will bring its schema up to
> date. If it's already Frankfurt, just reuse it.

Grant the runtime + build service accounts read access to the secrets:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

for SA in \
  "$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  "$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" ; do
  for S in DATABASE_URL GOOGLE_CLIENT_ID BACKEND_JWT_SECRET INTERNAL_SCHEDULER_SECRET CORS_ORIGINS ; do
    gcloud secrets add-iam-policy-binding $S \
      --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
  done
done

# Cloud Build also needs to deploy to Cloud Run and act as the runtime SA.
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role=roles/run.admin
gcloud iam service-accounts add-iam-policy-binding \
  $PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser
```

## Part 2 — First image build

```bash
gcloud builds submit backend \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/familybank/familybank-backend:bootstrap
```

## Part 3 — First deploy (sets env + secrets; done once)

```bash
gcloud run deploy familybank-backend \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/familybank/familybank-backend:bootstrap \
  --region=$REGION \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --timeout=60 \
  --set-env-vars=DEFAULT_BASE_CURRENCY=USD,DEV_MODE=false,SCHEDULER_ENABLED=false,SCHEDULER_INTERVAL_HOURS=5,REFRESH_STALENESS_THRESHOLD_HOURS=10,FRONTEND_BASE_URL=https://<canonical-frontend-domain> \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,BACKEND_JWT_SECRET=BACKEND_JWT_SECRET:latest,INTERNAL_SCHEDULER_SECRET=INTERNAL_SCHEDULER_SECRET:latest,CORS_ORIGINS=CORS_ORIGINS:latest
```

Key choices:
- **`--max-instances=2` / `--timeout=60`** — cost ceiling. Caps a
  runaway-traffic worst case at 2 containers (vs. no ceiling), and kills
  a stuck request after 60s instead of holding a container for the
  default 300s (the slowest real endpoint, `/internal/refresh`, runs
  ~5s). Pair with a GCP Billing budget + email alert (Billing → Budgets
  & alerts) — this bounds cost, the budget alert tells you fast if
  something's actually wrong.
- **`SCHEDULER_ENABLED=false`** — the in-process loop is off; Cloud
  Scheduler drives the refresh now. The staleness fallback in the app
  code covers a missed run.
- **`FRONTEND_BASE_URL`** (plain env var, not a secret — it's a public
  URL) — set it explicitly to the canonical frontend domain. Kid-login
  builds the parent's invite link from this; unset, it falls back to the
  first `CORS_ORIGINS` entry, which has already pointed invite links at
  the wrong (old vercel.app) domain in production once. `KID_JWT_TTL_DAYS`
  / `KID_INVITE_TTL_HOURS` / `KID_CLAIM_MAX_ATTEMPTS` have sane defaults
  and don't need setting.

Run migrations against the (Frankfurt) DB once:

```bash
gcloud run services proxy familybank-backend --region=$REGION &  # or run alembic locally
# locally, with the Frankfurt DATABASE_URL exported:
cd backend && alembic upgrade head
```

(After this, `cloudbuild.yaml` does migrations automatically on every
deploy.)

Grab the service URL:

```bash
SERVICE_URL=$(gcloud run services describe familybank-backend --region=$REGION --format='value(status.url)')
echo $SERVICE_URL
curl -s $SERVICE_URL/health   # -> {"status":"ok"}
```

Smoke-test the refresh endpoint:

```bash
curl -s -X POST $SERVICE_URL/internal/refresh \
  -H "X-Scheduler-Secret: <INTERNAL_SCHEDULER_SECRET value>"
# -> {"status":"ok"} ; check logs show "Scheduler refresh complete"
```

## Part 4 — Auto-deploy on push to master

Connect the GitHub repo to Cloud Build and add a trigger:

```bash
gcloud builds triggers create github \
  --repo-name=<repo> --repo-owner=<owner> \
  --branch-pattern='^master$' \
  --build-config=cloudbuild.yaml \
  --region=$REGION
```

(First time, the console will walk you through installing the Cloud Build
GitHub App on the repo.)

From now on: merge to `master` → build → migrate → deploy, zero-downtime
revision switch. Same as Render today.

## Part 5 — Cloud Scheduler (the cron)

```bash
gcloud scheduler jobs create http familybank-price-refresh \
  --location=$REGION \
  --schedule='1 */3 * * *' \
  --time-zone=UTC \
  --uri="$SERVICE_URL/internal/refresh" \
  --http-method=POST \
  --headers="X-Scheduler-Secret=<INTERNAL_SCHEDULER_SECRET value>" \
  --attempt-deadline=120s \
  --max-retry-attempts=1
```

That's the whole cron. Every 3 h, one job (well within Cloud Scheduler's
3-free-jobs tier). The boost math doesn't care about the exact cadence
(it prorates by real elapsed time between `price_ticks` — see
`boost_service._walk`), so this is purely "keep prices reasonably
fresh," not a market-timing decision.

## Part 6 — Daily database backup

Neon free-tier keeps only a **6 h** history window (the slider in Neon →
Settings → History window maxes at 6h; 30 days needs a paid plan). That's
not enough, so `.github/workflows/db-backup.yml` runs `pg_dump` daily via
GitHub Actions and keeps each dump as a **workflow artifact for 90 days**.

Chosen over a Cloud Run Job: no image to build, no service account key,
nothing in the GCP console — it reuses infra the repo already has, and a
GitHub artifact is a fine place for a <1 MB gzipped dump.

**Setup (one-time):**

1. Neon dashboard → your **production** project → Connection Details →
   copy the connection string. It's the **libpq** form
   (`postgresql://USER:PASS@HOST/neondb?sslmode=require`) — *not* the
   `postgresql+asyncpg://` form the app uses.
2. GitHub → repo → **Settings → Secrets and variables → Actions → New
   repository secret**: name `BACKUP_DATABASE_URL`, value = that string.
3. GitHub → **Actions → DB backup → Run workflow** to test it now. Check
   the run's **Artifacts** for `db-backup`.

After that it runs itself at 02:17 UTC daily.

### Restoring a backup

A dump is one gzipped file of plain SQL — every `CREATE TABLE` and every
`INSERT` needed to rebuild the database exactly as it was when the dump
ran. To use one:

1. **Get the file:** GitHub → Actions → DB backup → the run for the date
   you want → Artifacts → download `db-backup` →
   `familybank-YYYYMMDD-HHMMSS.sql.gz`.
2. **Never restore straight over production.** Restore into a **scratch**
   database first:
   - Neon → your project → **Branches → New branch** (a copy-on-write
     clone, free) → copy *its* connection string, or
   - a local Postgres / a throwaway Neon project.
3. **Restore:**
   ```bash
   gunzip -c familybank-YYYYMMDD-HHMMSS.sql.gz | psql "postgresql://…scratch-db…"
   ```
   (Restore into an *empty* target — the dump has no `DROP`s.)
4. **Then decide:**
   - *Recover a few rows* (a kid deleted by mistake, say): query the
     scratch DB, copy just those rows back into production by hand.
   - *Full rollback* (bad migration, wide corruption): point the app at
     the restored branch by updating the `DATABASE_URL` secret in GCP
     Secret Manager (new version) and redeploying, or promote the Neon
     branch. This loses everything written since the dump — last resort.

For anything inside the last 6 h, Neon's own **Restore** (Branches → the
branch → Restore, pick a timestamp) is finer-grained than the daily dump
— use that first when the incident is recent.

## Part 7 — Monitoring (the real "cron died" signal) — REMOVED, tried and reverted

The staleness fallback covers a missed run or two; it does not tell you
the scheduler is dead, so an alert was worth having in principle. What
was actually tried:

- Log-based metric `price_refresh_complete`, counting
  `resource.type="cloud_run_revision" AND "Scheduler refresh complete"`.
- Alert policy "Price refresh stopped" — condition type *Metric
  absence*, trigger `6h`.

**Deleted after it false-fired twice in under 2 days** while
`gcloud logging read 'resource.type="cloud_run_revision" AND
resource.labels.service_name="familybank-backend" AND textPayload:
"Scheduler refresh complete"' --freshness=2d --order=asc
--format="value(timestamp)"` proved the refresh had run on every single
3-hourly slot with zero real gaps. Root cause: `conditionAbsent` on a
log-derived metric that only emits a point every ~3h (naturally
mostly-empty alignment buckets) is a known-flaky combination in Cloud
Monitoring — it misfires independent of actual health. An alert nobody
trusts is worse than no alert, so it was removed rather than tuned.

**If revisited**, don't repeat this shape. Better options:
- Alert on Cloud Scheduler's own native metric
  `cloudscheduler.googleapis.com/job/attempt_count` filtered to failed
  attempts (threshold, not absence) — a real Monitoring metric, not a
  log-derived one, doesn't have this failure mode. Blind spot: doesn't
  catch the scheduler being disabled entirely (zero attempts, not a
  failed one).
- Or accept that `spawn_refresh_if_stale` (in the app itself) is the
  real safety net and skip external alerting altogether — it already
  guarantees prices are never more than ~10h stale regardless of what
  the external cron does.

The email notification channel (`familybank alerts`) is still there and
works (proven — it delivered both false-alarm emails); reuse it if a
replacement alert is built.

## Part 8 — Cutover — DONE (2026-09-11)

1. ✅ Deployed to Cloud Run, `/health` and a manual `/internal/refresh`
   both verified (~5s round-trip, ~9ms/query — vs. Render's 300-450ms).
2. ✅ Frontend repointed: Vercel `BACKEND_URL` / `NEXT_PUBLIC_BACKEND_URL`
   → the Cloud Run URL, both re-created as **Config** type (not Secret —
   a `NEXT_PUBLIC_*` var is browser-exposed by design, Vercel warns if
   it's marked Secret). Redeployed.
3. ✅ `CORS_ORIGINS` includes the canonical frontend domain
   (`familybank.kithcraft.com`) plus the Vercel domain.
4. ✅ Confirmed via Cloud Run logs: real browser traffic (`/home`,
   `/catalog`, `/kids/.../portfolio`, `/kids/.../savings`) all `200`.
   Scheduled refresh confirmed firing every 3h with zero gaps over a full
   day (`gcloud logging read` — see Part 7 for the exact command).
5. ✅ Render: `SCHEDULER_ENABLED=false` set.
6. **Not done — deliberately.** Render is being kept alive a while
   longer as a standby/rollback path (it's free tier, $0 cost to leave
   running). Revisit deleting it after a longer soak; not urgent.

## Rollback

Point the two Vercel env vars back at the Render URL and redeploy the
frontend; re-enable Render's scheduler. Everything else (DB, secrets) is
unchanged. Keep Render around until this is clearly not needed.

## Open follow-ups (not this migration)

- **Replace the Yahoo price fetch** (`app/services/price_client.py`) with
  a provider that has an SLA. Deliberately sequenced *after* this
  migration so a break is attributable to one change at a time. Consider
  coverage of `TA35.TA` / `^STOXX` and historical-tick support when
  evaluating. Not started.
- **Decommission Render** once the standby period feels long enough —
  delete the service, remove/decomission `render.yaml`.
- **Backups off GitHub Actions, onto GCP** (Cloud Run Job + GCS) if
  "a second system to remember" keeps bothering you — explicitly
  deferred, not urgent. See Part 6.
- **A real "cron died" alert**, done right this time (Cloud Scheduler's
  own `job/attempt_count` metric, not a log-derived absence check) — see
  Part 7 for what was tried and why it was removed.
- `max-instances=2` (tightened from the initial `4` for cost control —
  see the chat history / commit messages around 2026-09-10 for the
  reasoning). Raise it if real usage ever needs more headroom; watch
  Cloud Run's own instance-count metric rather than guessing.
