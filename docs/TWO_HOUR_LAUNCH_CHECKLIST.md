# APIx: two-hour launch checklist

Start the clock after the documentation checkpoint below. This plan targets a fully deployed, honestly demonstrated SIH MVP. Completing it does not guarantee finalist selection or establish production-scale reliability. Boxes remain unchecked until evidence is recorded. A working live source and deployment credentials are critical dependencies, not assumed successes.

## Documentation checkpoint — before T+0

- [ ] B: reconcile the latest shared-main changes with API/web documentation: CPI reference updates, historical backfill, and remaining fare-MAPE defect.
- [ ] Aryan + B: settle the deployment target. The agreed stack is Render API, Vercel web and Supabase DB; newer Fly.io files do not establish a deployment or an approved change of target.
- [ ] B: ensure README, DEPLOY, LIMITATIONS and DEMO_FLOW describe the same stack, data mode and known limitations.
- [ ] A: attach direct official source URLs and verify the three committed CPI observations; distinguish months included in this repo from all months available publicly.
- [ ] B: record the integration commit. Preserve both engineers’ work; do not overwrite shared-main changes.

## T+0–15 minutes: remove blockers

These owner lanes can run concurrently if Aryan coordinates both engineers.

- [ ] Aryan: sign into the chosen hosting accounts and provide database credentials through service secrets or an ignored local file, never documentation or chat.
- [ ] A: correct the malformed GitHub Actions DATABASE_URL and verify connectivity without printing credentials.
- [ ] A: verify production tables, seed routes and separate pipeline-write/API-read roles.
- [ ] B: integrate the agreed release commit and verify the API can SELECT from the production database.
- [ ] Aryan: confirm presentation/video submission requirements and team details.

**Gate at minute 15:** database connectivity works from the pipeline and serving environment; hosting access is available. If not, public-launch completion is blocked and must be reported immediately.

## T+15–45 minutes: real data and public services

### Engineer A — data plane

- [ ] Time-box one permitted live source or authorized feed. Implement parsing and a saved-response regression test; do not bypass access restrictions.
- [ ] Run a small live collection and verify route, departure date, carrier, currency, total fare and collection timestamp against the source.
- [ ] Persist actual observations with is_synthetic=false; failures must appear in scrape_runs.
- [ ] Keep simulation separate. Do not relabel generated history as observed data.
- [ ] Fix fare MAPE to compare route/month average fares in INR against verified INR references, or keep that metric unavailable for this release.

### Engineer B — serving and deployment

- [ ] Deploy the API with production database mode, secrets, exact CORS origins and health checks.
- [ ] Verify public health and /docs; test unauthorized 401 and authorized data responses.
- [ ] Deploy the web app with the public HTTPS API base and public read-only demo key.
- [ ] Verify database permissions restrict the serving role to required reads.

**Gate at minute 45:** public API and web URLs exist; live-source success or failure is evidenced. If no live source works, retain an explicitly simulated prototype and do not mark live MVP readiness complete.

## T+45–75 minutes: full integration and correctness

- [ ] A: run the daily workflow successfully against persistent production storage; confirm its rows survive the job ending.
- [ ] A: verify rerunning the collection does not introduce duplicate clean observations; verify one source failure does not erase successful results.
- [ ] A: add targeted regression coverage for 10% tail trimming, calendar gaps, seven-calendar-day baseline and canonical route IDs.
- [ ] B: verify overview, heatmap, lead curve, carriers, scraper health, methodology and API examples against the deployed API.
- [ ] B: verify live-only and combined modes independently; no synthetic data leaks into live-only views.
- [ ] B: expose freshness and coverage limitations clearly. Sparse live data must not imply full-basket coverage or validated historical accuracy.
- [ ] B: verify backtest caveats remain visible; two overlapping months cannot support a meaningful accuracy claim.
- [ ] B: run CI against the exact release commit and fix launch-blocking failures.

**Gate at minute 75:** a successful production pipeline run is visible through the public dashboard; calculations and provenance checks pass.

## T+75–100 minutes: launch checks and evidence

- [ ] B: test the public dashboard on laptop and phone, including loading, empty and API-failure states.
- [ ] B: verify CORS, HTTPS, key rejection and browser network requests use the correct public endpoint.
- [ ] B: measure warm-load and cold-start behavior; record actual results rather than claiming an unmeasured latency target.
- [ ] A + B: confirm scheduled-run failure notifications reach an owner and document where to inspect failures.
- [ ] A: confirm database backup/recovery arrangements and preserve a recoverable pre-demo dataset.
- [ ] B: record rollback steps and the last known working deployment/commit.
- [ ] B: update README with verified public URLs; save deployed screenshots, CI link and successful daily-run link.

## T+100–120 minutes: freeze and demonstrate

- [ ] Freeze features; fix only blockers affecting the demo or correctness.
- [ ] Aryan + B: rehearse DEMO_FLOW end to end using public URLs.
- [ ] Aryan: prepare slides covering problem, architecture, methodology, working evidence, limitations and next steps.
- [ ] Aryan: record the demo and verify the video link is accessible to the intended audience.
- [ ] Aryan: check all required submission fields, repository access, team details and deadline; submit only when ready.
- [ ] A + B: report any failed gate explicitly, with an owner and next action.

## Release acceptance — every item needs evidence

| Requirement | Evidence to record | Status |
|---|---|---|
| Public dashboard | HTTPS URL + phone/laptop check | Pending |
| Public API | HTTPS /docs URL + auth checks | Pending |
| Persistent database | Verified API reads and pipeline writes | Pending |
| Live collection | Successful source run + observed quote sample | Pending |
| Scheduled pipeline | Successful production Actions run URL | Pending |
| Data provenance | Live-only/combined checks + visible labels | Pending |
| Index correctness | Targeted regression results + CI commit | Pending |
| Honest backtesting | Verified references; invalid metrics unavailable | Pending |
| Operational recovery | Failure owner, backup and rollback notes | Pending |
| Demo and submission | Rehearsal, video and required submission checks | Pending |

“100%” here means all agreed MVP acceptance gates above pass. Multi-week reliability, statistically meaningful validation from observed history, multi-source resilience, load testing and institutional adoption cannot be established in two hours. Track those separately after launch; do not present them as completed.
