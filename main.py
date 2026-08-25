from fastapi import FastAPI
from pydantic import BaseModel
from scrapling.fetchers import StealthyFetcher
import re

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

def extract_emails(text: str) -> list:
    # Robust email regex pattern
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    # Proper deduplication: lowercase, remove duplicates, and sort
    unique_emails = sorted(list(set(email.lower() for email in emails)))
    return unique_emails

@app.post("/scrape")
async def scrape_email(request: ScrapeRequest):
    try:
        # Ensure URL has http/https
        url = request.url if request.url.startswith('http') else f'https://{request.url}'
        
        # ADVANCED: StealthyFetcher bypasses Cloudflare, Datadome, and basic anti-bot
        page = StealthyFetcher.fetch(url, headless=True, solve_cloudflare=True)
        
        # Extract all visible text content from the page
        text_content = page.text
        
        emails = extract_emails(text_content)
        
        return {
            "website": url,
            "emails": ", ".join(emails) if emails else "No emails found",
            "status": "success"
        }
    except Exception as e:
        # Return 200 with error status so n8n doesn't crash the whole workflow on one bad URL
        return {
            "website": request.url,
            "emails": "Error scraping",
            "error_detail": str(e),
            "status": "error"
        }
