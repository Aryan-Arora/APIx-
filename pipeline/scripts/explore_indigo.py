"""One-off reconnaissance script — NOT part of the pipeline.

Opens goindigo.in's flight search in a real (headless) browser, performs
a one-way search for a route/date, and records every XHR/fetch response
the page makes. We use this to find IndiGo's real fare-search API
endpoint and response shape before writing a proper adapter, per
SCRAPING.md's "intercept the XHR/JSON responses" approach.

Usage:
    pip install playwright
    playwright install chromium
    python scripts/explore_indigo.py --origin BOM --dest DEL --date 2026-10-15

Writes a JSON file (indigo_recon_<timestamp>.json) with, for every
response of a plausible size/content-type: url, status, content-type,
and (for JSON responses) the body. Also prints a short summary to
stdout so you can paste it back for a first pass without opening the
file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Playwright is not installed. Run:\n"
        "  pip3 install playwright\n"
        "  playwright install chromium\n",
        file=sys.stderr,
    )
    sys.exit(1)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
    "APIx-Research-Prototype/0.1 (+contact: see SCRAPING.md)"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="BOM")
    ap.add_argument("--dest", default="DEL")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, default: 14 days from today")
    args = ap.parse_args()

    depart = args.date or (date.today().toordinal() + 14)
    if isinstance(depart, int):
        from datetime import timedelta
        depart = (date.today() + timedelta(days=14)).isoformat()

    captured: list[dict] = []

    def on_response(response):
        try:
            ctype = response.headers.get("content-type", "")
            url = response.url
            # Only look at same-origin-ish API calls, skip images/fonts/analytics.
            if any(skip in url for skip in (".png", ".jpg", ".svg", ".woff", "google", "facebook", "analytics", "doubleclick")):
                return
            entry = {"url": url, "status": response.status, "content_type": ctype}
            if "json" in ctype.lower():
                try:
                    body = response.json()
                    body_str = json.dumps(body)
                    entry["body_preview"] = body_str[:2000]
                    entry["body_len"] = len(body_str)
                    # Heuristic: fare data usually has "fare" or "price" or "amount" in it.
                    entry["looks_fare_related"] = any(
                        kw in body_str.lower() for kw in ("fare", "price", "amount", "flight", "segment")
                    )
                except Exception:
                    pass
            captured.append(entry)
        except Exception as e:
            print(f"  (error reading a response: {e})", file=sys.stderr)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA)
        page = context.new_page()
        page.on("response", on_response)

        search_url = (
            f"https://www.goindigo.in/booking/book-flight?"
            f"trip=1&fareType=R&origin={args.origin}&destination={args.dest}"
            f"&travelDate={depart}&adults=1&children=0&infants=0&cabinClass=ECONOMY"
        )
        print(f"Navigating to: {search_url}")
        try:
            page.goto(search_url, timeout=45000, wait_until="networkidle")
        except Exception as e:
            print(f"Navigation warning (continuing anyway): {e}")

        page.wait_for_timeout(8000)  # let async fare-search calls finish

        screenshot_path = Path(f"indigo_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"Screenshot saved to: {screenshot_path}")
        except Exception as e:
            print(f"Could not take screenshot: {e}")

        print(f"Page title: {page.title()!r}")
        body_text = page.inner_text("body") if page.query_selector("body") else ""
        print(f"Page body text (first 500 chars): {body_text[:500]!r}")

        browser.close()

    out_path = Path(f"indigo_recon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_path.write_text(json.dumps(captured, indent=2))

    fare_related = [c for c in captured if c.get("looks_fare_related")]
    print(f"\nCaptured {len(captured)} responses total, {len(fare_related)} look fare-related.")
    print(f"Full detail written to: {out_path}\n")
    print("=== Fare-related candidates (url + status + first 300 chars) ===")
    for c in fare_related[:10]:
        print(f"- [{c['status']}] {c['url']}")
        print(f"  {c.get('body_preview', '')[:300]}")
        print()

    if not fare_related:
        print("No obvious fare-related JSON responses captured. Possible reasons:")
        print("  - The site needs interactive clicks (not just a direct URL) to trigger search")
        print("  - Anti-bot detection blocked the page before it loaded real results")
        print("  - The URL/query-param format above doesn't match IndiGo's actual search flow")
        print(f"Check {out_path} for ALL captured responses (including non-JSON) for clues.")


if __name__ == "__main__":
    main()
