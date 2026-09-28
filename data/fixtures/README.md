# Fixtures

Saved HTML/JSON snapshots used by adapter unit tests. Since live scraping
adapters are stubs in this build (see `docs/SCRAPING.md`), this directory
holds minimal placeholder fixtures only, enough to exercise the stub
adapters' parsing paths once real implementations land.

- `simulator_sample.json` — a small sample of simulator-generated quotes,
  used to sanity-check the shape consumed by `cleaning.py`.
