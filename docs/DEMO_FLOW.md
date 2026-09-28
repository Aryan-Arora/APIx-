# Demo flow — 1920 × 1080

Before recording: start/open the API and check `/api/v1/health`; wait for a sleeping Render instance. Open the dashboard at 1920×1080, zoom 100%, and confirm the top-right source indicator. Never describe mock fixtures as live data. If no populated DB is connected, introduce this as the serving-plane prototype.

1. **Overview:** show the headline and chart. Say “This measures relative price movement across a fixed route and booking-horizon basket. Base is 100.” Identify the current data mode and index date.
2. Toggle **Include simulated history** off. In mock mode, show the honest live-only empty state. If live observations exist, describe only the rows actually returned. Toggle it back on.
3. Click **weekly**, then **monthly**, then **daily**. Explain these are averages of pipeline daily indices.
4. Click **Sector heatmap** in the left navigation. Focus or hover a cell. Switch the measure to **Average fare (INR)**, then back to **Price index**. Explain the units differ.
5. Click **Lead-time elasticity**. Select BOM-DEL. Read the T+1/T+45 comparison and clarify that this is a cross-sectional comparison, not a booking guarantee.
6. Click **Reference backtest**. Read the provenance and reference status. If unavailable, state “We have not claimed a validated accuracy score.” Explain the CPI transport group's broader scope and units.
7. Click **Data quality**. Describe actual statuses only. An empty mock run log is intentional.
8. Click **Methodology**, then **API access**. Open interactive docs. Copy the shown curl command into a terminal. A live-only empty array is an honest response when no real index exists.
9. Close on the prototype label and provenance disclaimer.

Screenshot targets: `docs/img/overview-desktop.png`, `heatmap-desktop.png`, `lead-curve-desktop.png`, `overview-mobile.png`. Screenshots must show the real current data-mode labels.
