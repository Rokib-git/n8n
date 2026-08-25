// Free, self-hosted Google Maps rendering service.
// Renders the page with a real headless Chromium instance (like ScrapingAnt did),
// so Maps' JS-loaded listings actually show up - but at zero per-request cost.
//
// Response shape matches what the n8n workflow already expects:
//   { "data": "<full rendered HTML string>" }
// so the only change needed in n8n is which URL the HTTP Request node calls.

const express = require('express');
const { chromium } = require('playwright');

const app = express();
const PORT = process.env.PORT || 3000;

// A shared, long-lived browser instance is much faster than launching a
// fresh browser per request - launch is the slow part (~1-2s), a new
// page/context on an existing browser is cheap (~50-100ms).
let browserPromise = null;
async function getBrowser() {
  if (!browserPromise) {
    browserPromise = chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    });
  }
  return browserPromise;
}

app.get('/scrape', async (req, res) => {
  const targetUrl = req.query.url;
  // How long to let Maps' async listing data load in after the page shell
  // arrives. 4s is a reasonable default; bump via ?wait=6000 if listings are
  // still coming back empty for a particular query.
  const waitMs = Math.min(parseInt(req.query.wait, 10) || 4000, 15000);

  if (!targetUrl) {
    return res.status(400).json({ error: 'Missing required "url" query parameter' });
  }

  let context;
  try {
    const browser = await getBrowser();
    context = await browser.newContext({
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
      viewport: { width: 1366, height: 900 },
      locale: 'en-US',
    });
    const page = await context.newPage();

    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });

    // Let Maps' XHR-loaded results panel populate.
    await page.waitForTimeout(waitMs);

    // Nudge lazy-loaded listings by scrolling the results panel a bit.
    try {
      await page.mouse.wheel(0, 2000);
      await page.waitForTimeout(1000);
    } catch (e) {
      // Non-fatal - proceed with whatever loaded.
    }

    const html = await page.content();
    await context.close();
    context = null;

    return res.json({ data: html });
  } catch (err) {
    if (context) {
      try {
        await context.close();
      } catch (e) {
        /* ignore */
      }
    }
    return res.status(500).json({ error: String((err && err.message) || err) });
  }
});

app.get('/health', (req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Free Maps scraper listening on port ${PORT}`);
});

process.on('SIGTERM', async () => {
  if (browserPromise) {
    const browser = await browserPromise;
    await browser.close();
  }
  process.exit(0);
});
