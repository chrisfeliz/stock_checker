import os
import re
import sys
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from requests import Response


@dataclass(frozen=True)
class CheckResult:
    url: str
    in_stock: bool
    reason: str
    title: str | None


DEFAULT_URL = "https://www.mlbshop.com/new-york-mets/womens-new-york-mets-47-royal-confetti-clean-up-adjustable-hat/t-36772175+p-4878066661119+z-9-1161232641"


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _should_fallback_to_browser(resp: Response | None, exc: Exception | None) -> bool:
    if exc is not None:
        return True
    if resp is None:
        return True
    return resp.status_code in (401, 403, 429)


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_html_playwright(url: str) -> str:
    # Import lazily so local runs without Playwright installed still work.
    from playwright.sync_api import sync_playwright  # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            timeout=60000,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Give client-side PDP scripts time to render availability.
            page.wait_for_timeout(3000)
            return page.content()
        finally:
            context.close()
            browser.close()


def check_stock(url: str, html: str) -> CheckResult:
    soup = BeautifulSoup(html, "html.parser")

    title = None
    if soup.title and soup.title.string:
        title = _normalize_whitespace(soup.title.string)

    text = _normalize_whitespace(soup.get_text(" "))
    lower = text.lower()

    # Heuristics for Fanatics/MLBShop PDPs. Wording varies by locale and A/B tests.
    out_of_stock_markers = [
        "out of stock",
        "sold out",
        "currently unavailable",
        "this item is out of stock",
    ]
    in_stock_markers = [
        "add to cart",
        "add to bag",
    ]

    # Try to find a disabled add-to-cart button as a stronger signal.
    disabled_cart_button = soup.select_one(
        "button[disabled][data-talos='addToCart'], button[disabled][data-testid*='add'], button[disabled][name*='add']"
    )

    if any(m in lower for m in out_of_stock_markers):
        return CheckResult(url=url, in_stock=False, reason="Detected out-of-stock text on page", title=title)

    if disabled_cart_button is not None:
        return CheckResult(url=url, in_stock=False, reason="Add-to-cart button appears disabled", title=title)

    if any(m in lower for m in in_stock_markers):
        return CheckResult(url=url, in_stock=True, reason="Detected add-to-cart text on page", title=title)

    # Fallback: unknown status, treat as not in stock (and keep logs for debugging).
    return CheckResult(url=url, in_stock=False, reason="No clear stock signal found", title=title)


def main() -> int:
    url = os.environ.get("PRODUCT_URL", DEFAULT_URL).strip()
    try:
        use_browser = os.environ.get("USE_BROWSER", "1").strip() not in ("0", "false", "False")
        resp: Response | None = None
        exc: Exception | None = None
        html: str | None = None

        if not use_browser:
            html = fetch_html(url)
        else:
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                resp = requests.get(url, headers=headers, timeout=30)
                if _should_fallback_to_browser(resp, None):
                    html = fetch_html_playwright(url)
                else:
                    resp.raise_for_status()
                    html = resp.text
            except Exception as e:
                exc = e
                html = fetch_html_playwright(url)

        if html is None:
            raise RuntimeError("Failed to fetch HTML")

        result = check_stock(url, html)
    except Exception as e:
        # Keep scheduled runs "green" while still emitting a greppable line.
        msg = _normalize_whitespace(str(e)) or e.__class__.__name__
        print(f"status=ERROR reason={msg} title=n/a url={url}")
        return 0

    # Always print a single-line, greppable status.
    status = "IN_STOCK" if result.in_stock else "OUT_OF_STOCK"
    print(f"status={status} reason={result.reason} title={result.title or 'n/a'} url={result.url}")

    # Exit code 0 always so scheduled jobs don't get marked as failed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
