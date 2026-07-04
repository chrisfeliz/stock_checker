# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A small, single-purpose scraper: it checks one MLBShop product page for stock availability and
emails an alert when the item becomes available. There is no app server, database, or test suite —
just two scripts and two GitHub Actions workflows that run them on a schedule.

## Commands

```bash
# Local setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # needed for the headless-browser fallback

# Run a stock check (prints one status line, always exits 0)
python check_stock.py

# Send a one-off email using the same SMTP env vars the workflow uses
python send_email.py
```

There is no test suite, linter, or build step configured in this repo. Verify changes by running
`check_stock.py` locally and inspecting the printed status line.

## Architecture

### `check_stock.py`

- `main()` picks the URL from `PRODUCT_URL` env var (falls back to `DEFAULT_URL`), fetches the page,
  and prints exactly one line in the form `status=<...> reason=<...> title=<...> url=<...>`. This is
  meant to be greppable by the CI step that decides whether to send an alert (see workflow below).
- Fetch strategy: `USE_BROWSER` (default `"1"`) controls whether to try a plain `requests.get()`
  first and fall back to Playwright, or skip straight to `requests`. `_should_fallback_to_browser`
  triggers the Playwright path on request exceptions or on 401/403/429 responses, since MLBShop
  blocks simple scrapers.
- `fetch_html_playwright` imports `playwright.sync_api` lazily inside the function so that local runs
  without Playwright installed still work when `USE_BROWSER=0`.
- `check_stock()` parses the page with BeautifulSoup and decides in-stock/out-of-stock using text
  heuristics (`out_of_stock_markers`, `in_stock_markers`) plus a CSS selector for a disabled
  add-to-cart button. Out-of-stock markers are checked first (stronger signal), then the disabled
  button, then in-stock text; anything else falls through to "no clear stock signal found" (treated
  as not in stock). These heuristics are brittle by nature — MLBShop/Fanatics wording and DOM
  structure vary by A/B test, so expect to need to extend these lists rather than assume a single fix
  covers all cases.
- `main()` swallows all exceptions and always returns 0 / prints `status=ERROR ...` instead of
  raising, so that scheduled GitHub Actions runs stay "green" even when the site is unreachable or
  markup changes. Don't reintroduce non-zero exit codes for scrape failures — that's intentional.

### `send_email.py`

- Standalone script driven entirely by environment variables (`SMTP_HOST`, `SMTP_PORT`,
  `SMTP_SENDER`, `SMTP_PASSWORD`, `SMTP_RECEIVER`, `ALERT_SUBJECT`, `ALERT_BODY`). No CLI args.
- Port 465 uses implicit TLS (`SMTP_SSL`); any other port uses `STARTTLS`. Defaults assume Gmail
  (`smtp.gmail.com:465`), which requires an App Password rather than the account password.
- Has no knowledge of stock-checking; it just sends whatever subject/body it's given. The two
  scripts are only linked by the workflow that invokes them in sequence.

### `.github/workflows/stock-check.yml`

This is the actual production schedule and is the source of truth over the README (which describes
an older hourly cadence): cron runs every 6 hours (`17 */6 * * *`), plus `workflow_dispatch` for
manual runs. Steps:

1. Install deps + Playwright chromium.
2. Sleep a random 0–900s jitter before checking, to avoid a predictable request pattern.
3. Run `check_stock.py`, capture its single output line into the `line` job output via
   `$GITHUB_OUTPUT` heredoc syntax.
4. Conditionally run `send_email.py` only `if: contains(steps.run.outputs.line, 'status=IN_STOCK')`,
   passing SMTP secrets and a hardcoded subject/body describing this specific product.

If you change the printed status line format in `check_stock.py`, update the `contains(...)` check in
this workflow — they're coupled by string matching, not a shared constant.

### `.github/workflows/test-email.yml`

Manual-only (`workflow_dispatch`) workflow that calls `send_email.py` directly with a fixed test
subject/body, for verifying SMTP secrets are configured correctly without waiting for a real stock
change.

## Conventions worth preserving

- Both scripts read all configuration from environment variables/GitHub Secrets — never hardcode
  credentials, and don't add a config file or CLI arg parser for these.
- `check_stock.py` must keep failing "softly" (exit 0, `status=ERROR` line) — this is deliberate so
  scheduled runs don't show as failed CI just because the target site had a hiccup.
- The workflow's alert-triggering logic depends on the exact `status=IN_STOCK` substring printed by
  `check_stock.py`; keep the two in sync if either changes.
- `PRODUCT_URL` is duplicated in three places today: `DEFAULT_URL` in `check_stock.py`, the workflow's
  `PRODUCT_URL` env var, and the hardcoded URL in the workflow's `ALERT_BODY`. When changing the
  tracked product, update all three.
