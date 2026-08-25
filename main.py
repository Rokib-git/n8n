"""
Email Scraper API — powered by Scrapling (https://github.com/D4Vinci/Scrapling)

Given a website URL, this service:
  1. Tries a fast plain HTTP fetch first (Scrapling's Fetcher).
  2. Checks the homepage + common contact-style pages (/contact, /about, etc.)
  3. If nothing is found (or the site blocks plain requests), falls back to
     Scrapling's StealthyFetcher, which drives a hardened headless browser
     that bypasses most Cloudflare / bot-protection challenges.
  4. Extracts and cleans email addresses with regex, filtering out obvious
     junk (image filenames, tracking/CDN domains, etc.)

Deploy this on Render.com (see Dockerfile) and call POST /scrape from n8n.
"""

import re
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from scrapling.fetchers import Fetcher, StealthyFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email-scraper")

app = FastAPI(title="Scrapling Email Scraper API")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Pages most likely to list a business email. Homepage ("") is always tried
# first; we stop as soon as we find at least one email, to keep it fast.
CONTACT_PATHS = ["", "/contact", "/contact-us", "/contacts", "/about",
                  "/about-us", "/support", "/get-in-touch"]

# Domains that show up in scraped HTML but are never real contact emails
# (image CDNs, error trackers, placeholder/example addresses, etc.)
JUNK_EMAIL_DOMAIN_FRAGMENTS = [
    "example.com", "sentry.io", "wixpress.com", "godaddy.com",
    "schema.org", "w3.org", "yourdomain.com", "domain.com",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
]

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"
)

REQUEST_TIMEOUT_SECONDS = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    return raw.rstrip("/")


def extract_emails(html: str) -> set:
    if not html:
        return set()
    found = EMAIL_REGEX.findall(html)
    cleaned = set()
    for email in found:
        email = email.strip().strip(".").lower()
        if any(frag in email for frag in JUNK_EMAIL_DOMAIN_FRAGMENTS):
            continue
        # basic sanity: needs a dot in the domain part and no spaces
        domain = email.split("@")[-1]
        if "." not in domain or len(email) > 100:
            continue
        cleaned.add(email)
    return cleaned


def get_html_from_page(page) -> str:
    """Scrapling fetchers return an Adaptor/Response object. `.body` holds
    the raw page content (bytes on recent versions)."""
    body = getattr(page, "body", None)
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="ignore")
    return str(body)


def plain_fetch(url: str):
    try:
        return Fetcher.get(url, stealthy_headers=True, timeout=REQUEST_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.info("plain fetch failed for %s: %s", url, exc)
        return None


def stealthy_fetch(url: str):
    try:
        return StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=REQUEST_TIMEOUT_SECONDS * 1000,
        )
    except Exception as exc:
        logger.info("stealthy fetch failed for %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    url: str
    force_browser: bool = False  # skip straight to StealthyFetcher


class ScrapeResponse(BaseModel):
    url: str
    normalized_url: str
    emails: list
    pages_checked: int
    used_browser: bool
    error: str | None = None


@app.get("/")
def health():
    return {"status": "ok", "service": "scrapling-email-scraper"}


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest):
    base = normalize_url(req.url)
    if not base:
        return ScrapeResponse(
            url=req.url, normalized_url="", emails=[], pages_checked=0,
            used_browser=False, error="empty or invalid url",
        )

    all_emails: set = set()
    pages_checked = 0
    used_browser = False
    last_error = None

    fetch_order = [base + p for p in CONTACT_PATHS]

    # --- Pass 1: fast plain HTTP fetch across candidate pages -------------
    if not req.force_browser:
        for target in fetch_order:
            page = plain_fetch(target)
            pages_checked += 1
            if page is None:
                last_error = "plain fetch error"
                continue
            all_emails |= extract_emails(get_html_from_page(page))
            if all_emails:
                break  # good enough, stop early to save time

    # --- Pass 2: fall back to stealth browser if nothing found -----------
    if not all_emails:
        used_browser = True
        for target in fetch_order[:3]:  # homepage + first 2 contact paths only (slower)
            page = stealthy_fetch(target)
            pages_checked += 1
            if page is None:
                last_error = "stealthy fetch error"
                continue
            all_emails |= extract_emails(get_html_from_page(page))
            if all_emails:
                break

    return ScrapeResponse(
        url=req.url,
        normalized_url=base,
        emails=sorted(all_emails),
        pages_checked=pages_checked,
        used_browser=used_browser,
        error=None if all_emails else last_error,
    )
