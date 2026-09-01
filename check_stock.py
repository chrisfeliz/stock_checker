"""Check whether an Airbnb listing can be booked for a requested stay."""

import os
import re
from dataclasses import dataclass
from datetime import date, timedelta

from playwright.sync_api import Page, sync_playwright


# Keep these in sync with the env values in .github/workflows/airbnb-check.yml
DEFAULT_LISTING_URL = "https://www.airbnb.com/rooms/1693855865772640392"
DEFAULT_CHECKIN = "2026-10-09"
DEFAULT_NIGHTS = 1


@dataclass(frozen=True)
class CheckResult:
    url: str
    available: bool
    reason: str
    title: str | None
    checkin: date
    checkout: date


def requested_stay() -> tuple[date, date]:
    """Read and validate the requested check-in date and length of stay."""
    try:
        checkin = date.fromisoformat(os.environ.get("CHECKIN_DATE", DEFAULT_CHECKIN))
        nights = int(os.environ.get("NIGHTS", str(DEFAULT_NIGHTS)))
    except ValueError as exc:
        raise ValueError("CHECKIN_DATE must use YYYY-MM-DD and NIGHTS must be an integer") from exc
    if nights < 1:
        raise ValueError("NIGHTS must be at least 1")
    return checkin, checkin + timedelta(days=nights)


def calendar_label(day: date) -> str:
    return f"{day.day}, {day.strftime('%A, %B %Y')}"


def is_selectable(label: str | None, purpose: str) -> bool:
    """Interpret Airbnb's accessible calendar label without relying on CSS classes."""
    return bool(label and f"Available. Select as {purpose} date." in label)


def find_day_button(page: Page, target: date):
    pattern = re.compile(rf"^{re.escape(calendar_label(target))}")
    return page.get_by_test_id("bookit-sidebar-availability-calendar").get_by_role(
        "button", name=pattern
    )


def move_calendar_to(page: Page, target: date) -> None:
    """Advance Airbnb's two-month calendar until its target day is rendered."""
    calendar = page.get_by_test_id("bookit-sidebar-availability-calendar")
    for _ in range(24):
        if find_day_button(page, target).count():
            return
        calendar.get_by_role(
            "button", name="Move forward to switch to the next month."
        ).click(timeout=10_000)
        page.wait_for_timeout(250)
    raise RuntimeError(f"Could not navigate calendar to {target.isoformat()}")


def check_availability(url: str, checkin: date, checkout: date) -> CheckResult:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.get_by_role("button", name=re.compile("^Change dates;")).click(timeout=20_000)

            move_calendar_to(page, checkin)
            checkin_button = find_day_button(page, checkin)
            checkin_label = checkin_button.get_attribute("aria-label")
            if not is_selectable(checkin_label, "check-in"):
                return CheckResult(
                    url, False, checkin_label or "Check-in date was not found", page.title(), checkin, checkout
                )

            # A stay is only bookable when both endpoints can be selected.
            checkin_button.click(timeout=10_000)
            move_calendar_to(page, checkout)
            checkout_button = find_day_button(page, checkout)
            checkout_label = checkout_button.get_attribute("aria-label")
            available = is_selectable(checkout_label, "checkout")
            reason = (
                "Both check-in and checkout dates are selectable"
                if available
                else checkout_label or "Checkout date was not found"
            )
            return CheckResult(url, available, reason, page.title(), checkin, checkout)
        finally:
            context.close()
            browser.close()


def main() -> int:
    url = os.environ.get("LISTING_URL", DEFAULT_LISTING_URL).strip()
    try:
        checkin, checkout = requested_stay()
        result = check_availability(url, checkin, checkout)
    except Exception as exc:
        message = (re.sub(r"\s+", " ", str(exc)).strip() or exc.__class__.__name__)[:500]
        print(f"status=ERROR reason={message} url={url}")
        return 1

    status = "AVAILABLE" if result.available else "UNAVAILABLE"
    print(
        f"status={status} checkin={result.checkin.isoformat()} "
        f"checkout={result.checkout.isoformat()} reason={result.reason} "
        f"title={result.title or 'n/a'} url={result.url}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
