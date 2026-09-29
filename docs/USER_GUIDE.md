# User guide

Start with the data-source indicator at the top right. “Mock API · illustrative fixtures” means the page demonstrates the interface with generated examples. “Connected to shared database” describes the backend connection; use row provenance and source-health history to assess whether measurements are live.

The amber provenance strip contains “Include simulated history.” Enabled selects the combined index series and permits simulated quotes in fare aggregates. Disabled selects the live-only index and excludes synthetic quotes. Empty live-only panels are expected before collection succeeds. The toggle does not change scraper history or backtest evidence.

- **Overview:** headline APIx, exact 1/7/30-day changes, latest quote count, and daily/weekly/monthly series. Base is 100. Hover the chart for dates and values.
- **Sector heatmap:** switch between index points and average fare in INR. Latest 14 dates appear across canonical route pairs. Hover or keyboard-focus a cell for its value. Scroll the table horizontally on phones.
- **Lead-time elasticity:** select a route. T+1 means one day before departure; T+45 means 45 days. The callout compares average fares across booking horizons, not a guaranteed saving for one flight.
- **Carriers:** compares arithmetic average quotes and mean stored daily indices. Different route mixes can affect comparisons.
- **Reference backtest:** source notes, pipeline summary statistics and reference rows. Missing verified reference data is reported explicitly. CPI Transport & Communication is broader than aviation and uses index points, not rupees.
- **Data quality:** recorded collection attempts, failed/blocked status and error details. Mock mode does not fabricate scraper runs.
- **Methodology:** formula, weighting, missing-cell rules and limitations. Route weights remain assumptions until verified.
- **API access:** endpoint directory, an executable curl example and interactive OpenAPI documentation.

Use **Refresh data** after the pipeline runs or when a sleeping backend wakes up. A database failure appears as an error instead of showing mock numbers. Narrow-screen navigation opens with the menu button. All principal controls are keyboard accessible.

### Chart ranges and download

On Overview, choose Daily, Weekly or Monthly, then 2 weeks, 1 month or All history. The range is measured backwards from the latest available period date, not today's date. The footer shows the displayed date range and minimum/maximum index values. Export CSV downloads the currently displayed series, including frequency, quote count and the synthetic-data flag. Export is disabled while loading or when the selection has no observations.

On mobile, open the navigation menu to switch sections. Escape dismisses it and returns focus to the menu button. Reduced-motion preferences are respected.
