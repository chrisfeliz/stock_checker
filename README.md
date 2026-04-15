# stock_checker

Hourly stock check for an MLBShop product page, deployed via GitHub Actions.

## What it does

- Checks the product page once per hour.
- If it detects **IN STOCK**, it sends an email alert.
- Uses a headless browser (Playwright) because MLBShop often blocks simple HTTP scrapers.

## Deploy on GitHub (recommended)

1. Create a new GitHub repo (or use an existing one).
2. Put these files in the repo root:
   - `check_stock.py`
   - `requirements.txt`
   - `.github/workflows/stock-check.yml`
3. Push to GitHub.
4. In GitHub, go to **Actions** and enable workflows if prompted.
5. Add GitHub Secrets in **Settings → Secrets and variables → Actions**:
   - `SMTP_SENDER` (sender email address)
   - `SMTP_RECEIVER` (receiver email address)
   - `SMTP_PASSWORD` (email/app password)
  - Optional: `SMTP_HOST` (defaults to `smtp.gmail.com`)
  - Optional: `SMTP_PORT` (defaults to `465`)
6. (Optional) Click **Actions → Stock check (hourly) → Run workflow** to test immediately.

The workflow runs hourly (see cron in `.github/workflows/stock-check.yml`).

## Local run (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python check_stock.py
```

## Customize the URL

- Update `PRODUCT_URL` in `.github/workflows/stock-check.yml`, or
- Set a `PRODUCT_URL` environment variable locally.

## Notes for Gmail

- Use an **App Password** (not your normal account password) if 2FA is enabled.
- Default transport is Gmail SMTP over SSL (`smtp.gmail.com:465`).
- Keep all SMTP credentials in GitHub Secrets only.

