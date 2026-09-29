# Deployment — Vercel web, Render API, Supabase database

No hosting credentials belong in Git or shared chat logs. Configure secrets in the service dashboards or a local ignored environment file. The public `NEXT_PUBLIC_API_KEY` is intentionally visible to browser users and must only permit read access.

## 1. Database handoff (Engineer A)

1. Open the Supabase project and confirm Engineer A has provisioned the frozen tables and populated indices.
2. Click **Connect**, choose **Session pooler**, and copy the Postgres connection string. This supports persistent IPv4 backends. Use the serving SELECT-only database role supplied by A; URL-encode password characters.
3. Include `sslmode=require` at minimum. For certificate verification, use the project root certificate and `sslmode=verify-full`. Do not publish this URL.
4. Set it as `DATABASE_URL` in Render. The API accepts `postgresql://` and normalises it to the psycopg SQLAlchemy driver. It does not run migrations or seed data.
5. Ask A to verify Supabase Data API exposure/RLS and restrict public table access. B does not change schema or policies.

Reference: [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres). Session port is generally 5432; copy the actual project URL rather than constructing hostnames. Transaction pooler connections need prepared-statement handling and are not the default for this service.

## 2. Render API

The repository includes `render.yaml` for a free Docker service on `main`. Once this file is merged, choose **New → Blueprint**, connect the repository and enter `DATABASE_URL`, `API_KEYS` and `ALLOWED_ORIGINS` when prompted. It deploys database mode and uses `/api/v1/health` for health checks. Follow the endpoint checks below after provisioning. See the [Render Blueprint specification](https://render.com/docs/blueprint-spec). The manual equivalent follows.

1. Sign into Render. Choose **New → Web Service**.
2. Connect GitHub and choose `Aryan-Arora/APIx-`. Select the integration branch that contains both engineers' work; for an explicit mock preview use `feat/api-web`.
3. Name the service `apix-api` (or an available project-specific name). Choose a suitable region and **Docker** runtime.
4. Set **Root Directory** to `api`. Set **Dockerfile Path** to `./Dockerfile` and Docker build context to the root of that service (`api` in the repo). The Dockerfile copies `requirements.lock.txt` and `app/` relative to this context.
5. Select the free instance type if available. Do not upgrade to a paid instance without choosing that deliberately.
6. Add environment variables:
   - `USE_MOCK=0` for integrated DB mode; `1` only for an explicitly labelled fixture preview.
   - `DATABASE_URL` from the previous step (not needed in mock mode).
   - `API_KEYS`: comma-separated read-only keys, including the public demo key.
   - `ALLOWED_ORIGINS`: exact web origin(s), comma-separated, no trailing slash. Initially use the intended Vercel origin, then update to the assigned URL.
7. Set **Health Check Path** to `/api/v1/health`.
8. Create/deploy the service. Confirm `/api/v1/health` returns 200 and `db=connected`, `data_mode=database` for integrated mode. Mock mode returns `db=mock` and must be described as mock.
9. Open `/docs`, click **Authorize**, enter the demo key, and execute `/index`. Verify an unauthenticated data request returns 401.

The container uses Python 3.11, a non-root user and Render's `PORT`. It runs one worker. Proxy headers are disabled by default; see architecture limits. If Render does not offer a free Docker service for the account/region, stop and select a deployment plan with the human; do not silently incur charges.

## 3. Vercel dashboard

1. Sign into Vercel. Choose **Add New → Project** and import `Aryan-Arora/APIx-`.
2. Set **Root Directory** to `web`; framework preset **Next.js**; Node.js **22.x**.
3. Keep build command `npm run build`, install command `npm ci`, and automatic Next.js output settings.
4. Set `NEXT_PUBLIC_API_BASE=https://<render-service>.onrender.com/api/v1`.
5. Set `NEXT_PUBLIC_API_KEY` to the public read-only demo key configured in Render.
6. Deploy the desired branch. Keep account deployment protection settings; test previews using authenticated access as needed.
7. Copy the public production origin into Render's `ALLOWED_ORIGINS` and redeploy/restart the API.
8. Changing NEXT_PUBLIC variables requires a fresh web build. Verify the browser sends requests to the Render URL, not localhost.

CLI alternative, when Vercel authentication is present:

```bash
cd web
vercel whoami
vercel link
vercel env add NEXT_PUBLIC_API_BASE production
vercel env add NEXT_PUBLIC_API_KEY production
vercel --prod
```

Do not run a public build with a localhost API base. See [Vercel Next.js docs](https://vercel.com/docs/frameworks/full-stack/nextjs) and [Render Docker docs](https://render.com/docs/docker) for current hosting controls.

## 4. End-to-end acceptance

- `/health` states database mode and connected DB, and reports actual last scrape time.
- `/docs` loads; missing/wrong API key returns 401; valid key returns rows.
- Dashboard loads from its public URL on desktop and mobile; CORS succeeds.
- Toggle synthetic off and compare to `/index?include_synthetic=false`; no synthetic points leak.
- Inspect reference notes/units. No verified reference means no accuracy claim.
- Verify CI for the exact deployed commit, including pipeline tests after handoff.
- Save actual live URLs and the deployment commit in README.

Before a demo, request `/health` a minute ahead to wake a free Render instance. Avoid claiming a guaranteed sub-three-second cold start. No recurring keep-warm automation is installed by this scaffold.

## Session status (2026-09-29)

- GitHub repo: https://github.com/Aryan-Arora/APIx-, branch `feat/api-web`.
- Vercel CLI is authenticated; no APIx Vercel project was deployed while its API URL was unavailable.
- Render dashboard requires sign-in. No public API URL or production DATABASE_URL was supplied.
- Local dashboard: http://localhost:3000. Local API: http://localhost:8100/api/v1; docs: http://localhost:8100/docs. Port 8000 was already occupied by another application, so the local preview uses 8100.
- Local API is in `USE_MOCK=0` mode against root `apix-integration-20260929.db`, populated by A's simulator. The rows are synthetic, not live-scraped.
- To reproduce locally from the integrated branch: install `pipeline[dev]`, run `backfill --days 45`, `compute-index`, and `backtest` against an absolute SQLite DATABASE_URL; start the API with that same URL and set the web's `.env.local` base to the selected port. Commands and pipeline ownership remain as described above.

## Release verification and recovery

Run `API_BASE=https://<service>/api/v1 API_KEY=<read-only-key> python3 scripts/smoke_api.py` in an environment where secrets are supplied securely. The script verifies database health, auth rejection, response shapes and live-only index provenance. It never prints the key. A successful smoke check does not establish live-source coverage; inspect scraper health and quote provenance separately.

Record the exact deployed commit and both deployment identifiers. Before a change, retain the prior working deployment and confirm database recovery arrangements with the pipeline owner. If the web release fails, restore the previous Vercel deployment and its matching build-time API configuration. If the API fails, roll back to the previous Render deployment. Check health, auth, CORS and the dashboard again. API releases do not migrate the database; schema rollback and backups belong to the data-plane owner.

The newly integrated Fly.io files are an undeployed alternative configuration. Render/Vercel remains the documented launch target. No Fly.io provisioning or billing changes were performed. The web Docker context excludes local environment files and generated dependencies.
