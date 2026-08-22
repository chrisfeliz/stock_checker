# Airbnb availability checker

Checks whether this [Highland, NY Airbnb listing](https://www.airbnb.com/rooms/1693855865772640392) can be booked for a one-night stay beginning **October 9, 2026**. GitHub Actions runs every six hours and emails you when both the check-in and checkout dates become selectable.

The listing currently marks October 9 as checkout-only, so the alert will not fire until it becomes valid as a check-in date.

## Setup

Add these GitHub Actions secrets under **Settings → Secrets and variables → Actions**:

| Secret | Required | Description |
|---|---|---|
| `SMTP_SENDER` | Yes | Sending email address |
| `SMTP_RECEIVER` | Yes | Recipient email address |
| `SMTP_PASSWORD` | Yes | Email or app password |
| `SMTP_HOST` | No | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | No | Defaults to `465` (SSL) |

Enable Actions if prompted. Use **Actions → Test email alert → Run workflow** to validate SMTP, or run **Airbnb availability check** manually to test the calendar check.

## Change the stay

Update these values in [.github/workflows/stock-check.yml](.github/workflows/stock-check.yml):

- `CHECKIN_DATE` — ISO date, for example `2026-10-09`
- `NIGHTS` — number of nights, currently `1`
- `LISTING_URL` — Airbnb listing to monitor

The same values can be overridden locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

export CHECKIN_DATE="2026-10-09"
export NIGHTS=1
python check_stock.py
```

Airbnb can change its calendar UI or restrict automated traffic. In those cases the workflow fails visibly instead of reporting a false availability result.
