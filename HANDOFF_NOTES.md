# APIx integration notes

## Engineer A
- Engineer B is implementing the frozen schema using SELECT-only SQLAlchemy queries. No pipeline/data files are owned or modified by B.
- Backtest conflict: section 2 requests CPI Transport & Communication trend correlation; sections 5/6 and the frozen table still name DGCA fare/MAPE. Please populate source_note and summary notes with actual provenance; never store CPI index values as INR fares or calculate fare MAPE against CPI. B will render raw legacy fields with explicit units/provenance and no invented reference values. Schema changes require written agreement first.
- Canonical route IDs: alphabetically sorted airport pair; direction remains origin/dest. API accepts reversed route aliases.
- Please provide populated DATABASE_URL and schema handoff; B stays in explicit USE_MOCK=1 until then.
- Please confirm backtest summary metric spelling (B accepts MAPE/mape, correlation/corr, direction_agreement/direction).
- Supabase should expose no public table access unless explicitly intended; provision a SELECT-only database role for the serving API. B does not modify schema or policies.

## Engineer B
- Branch: feat/api-web. Working directory: /Users/aryanarora/Desktop/apix.
- Mock fixtures are generated only in API memory and explicitly labelled; real-only mode returns empty data in mock mode.
- Additive provenance fields and include_synthetic filters on quote-derived endpoints will prevent mode mixing; frozen index response fields are preserved.
