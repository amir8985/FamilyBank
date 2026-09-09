# Backend migration: Render → Cloud Run (Frankfurt)

Status: **planned / in progress.** Backend code changes (advisory lock,
staleness fallback, Dockerfile, `cloudbuild.yaml`) are done on branch
`perf-followups`. The GCP wiring below is not done yet.

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
  --max-instances=4 \
  --set-env-vars=DEFAULT_BASE_CURRENCY=USD,DEV_MODE=false,SCHEDULER_ENABLED=false,SCHEDULER_INTERVAL_HOURS=5 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,BACKEND_JWT_SECRET=BACKEND_JWT_SECRET:latest,INTERNAL_SCHEDULER_SECRET=INTERNAL_SCHEDULER_SECRET:latest,CORS_ORIGINS=CORS_ORIGINS:latest
```

Key choice: **`SCHEDULER_ENABLED=false`** — the in-process loop is off;
Cloud Scheduler drives the refresh now. The staleness fallback in the app
code covers a missed run.

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

Neon's free tier only keeps ~6 h of restore history. A daily logical dump
to GCS covers the gap. This *is* a good fit for a Cloud Run **Job** (pure
batch, no HTTP) — the objection to a Job for the refresh doesn't apply.

```bash
gsutil mb -l $REGION gs://$PROJECT_ID-db-backups
gsutil lifecycle set /dev/stdin gs://$PROJECT_ID-db-backups <<'EOF'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}
EOF
```

Create a tiny job image (`backend/backup/Dockerfile`, ~5 lines: a
`postgres:16` base + `google-cloud-cli`, entrypoint a script that runs
`pg_dump "$DATABASE_URL_LIBPQ" | gzip | gsutil cp - gs://.../$(date).sql.gz`).
Note `pg_dump` needs the **libpq** URL (`postgresql://...`), not the
asyncpg one — store it as a separate secret `DATABASE_URL_LIBPQ`.

```bash
gcloud run jobs create familybank-db-backup \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/familybank/familybank-db-backup:latest \
  --region=$REGION \
  --set-secrets=DATABASE_URL_LIBPQ=DATABASE_URL_LIBPQ:latest \
  --set-env-vars=BACKUP_BUCKET=$PROJECT_ID-db-backups

gcloud scheduler jobs create http familybank-db-backup-daily \
  --location=$REGION \
  --schedule='0 3 * * *' --time-zone=UTC \
  --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/familybank-db-backup:run" \
  --http-method=POST \
  --oauth-service-account-email="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
```

## Part 7 — Monitoring (the real "cron died" signal)

The staleness fallback covers a missed run or two; it does not tell you
the scheduler is dead. Add an alert:

- Cloud Monitoring → alerting policy on metric
  `cloudscheduler.googleapis.com/job/attempt_count` filtered to
  `response_code != 200` for `familybank-price-refresh` → notify by email.
- Optionally a second policy on the log-based signal: no
  `"Scheduler refresh complete"` log line in the last 14 h.

## Part 8 — Cutover

1. Deploy to Cloud Run, verify `/health` and a manual `/internal/refresh`.
2. Point the frontend at the new URL: Vercel → project → Settings →
   Environment Variables → set `BACKEND_URL` and
   `NEXT_PUBLIC_BACKEND_URL` to `$SERVICE_URL`. Redeploy the frontend.
3. Make sure `$SERVICE_URL`'s Vercel origin is in `CORS_ORIGINS` (it is
   if you kept the same Vercel domain).
4. Watch Cloud Run logs + `request_logs` for a day — confirm latency
   dropped and the scheduled refresh fires.
5. On Render: set `SCHEDULER_ENABLED=false` (or just suspend the
   service). Keep it suspended-but-alive for a few days as a fallback.
6. Once confident: delete the Render service. Remove `render.yaml`, or
   leave it with a "decommissioned" comment.

## Rollback

Point the two Vercel env vars back at the Render URL and redeploy the
frontend; re-enable Render's scheduler. Everything else (DB, secrets) is
unchanged. Keep Render around until this is clearly not needed.

## Open follow-ups (not this migration)

- **Replace the Yahoo price fetch** (`app/services/price_client.py`) with
  a provider that has an SLA. Deliberately sequenced *after* this
  migration so a break is attributable to one change at a time. Consider
  coverage of `TA35.TA` / `^STOXX` and historical-tick support when
  evaluating.
- Multi-instance: `max-instances` is 4. The in-process scheduler is off,
  so that's fine, but if anything else instance-affine is added later,
  re-check.
