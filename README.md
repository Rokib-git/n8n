# Scrapling Email Scraper API

A small FastAPI service, built on [Scrapling](https://github.com/D4Vinci/Scrapling), that takes a
website URL and returns the email addresses it can find on the homepage and common contact-style
pages. It tries a fast plain HTTP request first, and only falls back to a full stealth browser
(bypasses most Cloudflare / bot-protection) if nothing is found — this keeps it fast and free-tier
friendly while still handling protected sites.

## Deploy to Render.com (free tier)

1. Push this folder to a GitHub repo (public or private).
2. In Render: **New +** → **Blueprint** → connect the repo. Render will read `render.yaml` and
   deploy it automatically. (Or: **New +** → **Web Service** → Docker → point at this repo.)
3. First deploy takes a few minutes — it downloads the stealth browser during the build
   (`scrapling install`).
4. Once live, your endpoint is `https://<your-service>.onrender.com/scrape`.

**Note on the free tier:** Render's free web services spin down after ~15 minutes idle and take
~30-60s to wake back up on the next request. If your n8n workflow times out on the first call
after idle, either increase the HTTP Request node's timeout to ~60s, or upgrade to a paid instance
for always-on scraping.

## API

`POST /scrape`
```json
{ "url": "example.com", "force_browser": false }
```

Response:
```json
{
  "url": "example.com",
  "normalized_url": "https://example.com",
  "emails": ["hello@example.com"],
  "pages_checked": 1,
  "used_browser": false,
  "error": null
}
```

## Testing locally

```bash
pip install -r requirements.txt
scrapling install
uvicorn main:app --reload
curl -X POST http://localhost:8000/scrape -H "Content-Type: application/json" -d '{"url":"example.com"}'
```
