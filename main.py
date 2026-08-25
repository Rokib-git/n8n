"""
Email Scraper API — powered by Scrapling (https://github.com/D4Vinci/Scrapling)
Strictly follows Scrapling's Fetcher and StealthyFetcher methodologies.
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
# Pages most likely to list a business email.
PLAIN_CONTACT_PATHS = ["", "/contact", "/contact-us", "/about"]
STEALTH_CONTACT_PATHS = ["", "/contact"]

# Domains that show up in scraped HTML but are never real contact emails
JUNK_EMAIL_DOMAIN_FRAGMENTS = [
    "example.com", "sentry.io", "wixpress.com", "godaddy.com",
    "schema.org", "w3.org", "yourdomain.com", "domain.com",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
]

# Robust Email Regex
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"
)

# Timeouts (Seconds for Fetcher, Milliseconds for StealthyFetcher)
HTTP_TIMEOUT_SEC = 12
STEALTH_TIMEOUT_MS = 25000 

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw: return ""
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    return raw.rstrip("/")

def extract_emails(html: str) -> set:
    if not html: return set()
    cleaned = set()
    for email in EMAIL_REGEX.findall(html):
        email = email.strip().strip(".").lower()
        if any(frag in email for frag in JUNK_EMAIL_DOMAIN_FRAGMENTS): continue
        domain = email.split("@")[-1]
        if "." not in domain or len(email) > 100: continue
        cleaned.add(email)
    return cleaned

def get_html_from_page(page) -> str:
    """
    Scrapling fetchers return an Adaptor/Response object.
    We check .html, .text, and .body to be 100% compatible with all Scrapling versions.
    """
    if hasattr(page, "html") and page.html:
        return str(page.html)
    if hasattr(page, "text") and page.text:
        return str(page.text)
    
    body = getattr(page, "body", None)
    if body is None: return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="ignore")
    return str(body)

def page_status_ok(page) -> bool:
    # Scrapling response objects expose .status
    status = getattr(page, "status", 200) or 200
    return 200 <= status < 400

def plain_fetch(url: str):
    try:
        # Fetcher uses HTTPX under the hood. stealthy_headers=True spoofs standard headers.
        return Fetcher.get(url, stealthy_headers=True, timeout=HTTP_TIMEOUT_SEC)
    except Exception as exc:
        logger.info("plain fetch failed for %s: %s", url, exc)
        return None

def stealthy_fetch(url: str):
    try:
        # StealthyFetcher uses Patchright/Camoufox. 
        # network_idle=True is crucial for waiting out Cloudflare JS challenges.
        return StealthyFetcher.fetch(
            url, 
            headless=True, 
            network_idle=True,
            timeout=STEALTH_TIMEOUT_MS
        )
    except Exception as exc:
        logger.info("stealthy fetch failed for %s: %s", url, exc)
        return None

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class ScrapeRequest(BaseModel):
    url: str
    force_browser: bool = False

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

    # --- Pass 1: fast plain HTTP fetch -----------------------------------
    if not req.force_browser:
        for i, path in enumerate(PLAIN_CONTACT_PATHS):
            page = plain_fetch(base + path)
            pages_checked += 1
            if page is None:
                last_error = "plain fetch error"
                if i == 0: break  # site refuses plain HTTP -> go stealth
                continue
            if not page_status_ok(page): continue
            
            all_emails |= extract_emails(get_html_from_page(page))
            if all_emails: break

    # --- Pass 2: fall back to stealth browser -----------------------------
    if not all_emails:
        used_browser = True
        for path in STEALTH_CONTACT_PATHS:
            page = stealthy_fetch(base + path)
            pages_checked += 1
            if page is None:
                last_error = "stealthy fetch error"
                continue
                
            all_emails |= extract_emails(get_html_from_page(page))
            if all_emails: break

    return ScrapeResponse(
        url=req.url, normalized_url=base, emails=sorted(list(all_emails)),
        pages_checked=pages_checked, used_browser=used_browser,
        error=None if all_emails else last_error,
    )
