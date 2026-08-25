# Free Maps Scraper

A tiny, self-hosted replacement for ScrapingAnt. It runs a real headless
Chromium browser (via Playwright) so it sees the same JS-rendered Google Maps
results a normal browser sees — no per-request API cost, and no "please
enable JavaScript" wall.

It exposes one endpoint:

```
GET /scrape?url=<url-encoded target url>&wait=4000
```

Response (matches the shape ScrapingAnt returned, so nothing else in your n8n
workflow needs to change):

```json
{ "data": "<full rendered HTML string>" }
```

## Do you have SSH/Docker access to the server running n8n?

**Yes** → deploy it right there, on the same box, and it'll be effectively
free and fast (no network hop to a third party):

```bash
# 1. Copy this folder to your server, then:
cd maps-scraper
docker compose up -d --build

# 2. Test it:
curl "http://localhost:3010/scrape?url=https://www.google.com/maps/search/Plumber%20Boston"
# You should get back JSON with a big "data" field full of HTML.
```

If n8n also runs in Docker on that box, uncomment the `networks:` section in
`docker-compose.yml`, set it to n8n's Docker network name (find it with
`docker network ls`), and n8n can then call this service at
`http://maps-scraper:3000/scrape` directly by container name — no public port
needed at all.

If n8n is *not* in Docker (e.g. installed directly, or a managed host), just
use `http://<server-ip-or-domain>:3010/scrape` from the n8n HTTP Request node.
Make sure port `3010` is open in your firewall/security group for at least
n8n's own IP.

## No SSH/Docker access (managed n8n hosting)?

Some managed n8n hosts (shared platforms, etc.) don't give you a place to run
your own long-lived Docker container. If that's your situation, deploy this
same code to a small free-tier host instead — any of these work well with a
Dockerfile like this one:

- **Render.com** — free web service tier, connect a GitHub repo, it builds
  the Dockerfile automatically, gives you a public HTTPS URL.
- **Railway.app** — similar flow, generous free trial credits.
- **Fly.io** — free allowance, `fly launch` picks up the Dockerfile.

Push this folder to a GitHub repo, connect it on whichever platform you pick,
and use the public URL it gives you (e.g. `https://your-app.onrender.com/scrape`)
in the n8n HTTP Request node instead of a local address.

## Tuning

- `wait` query param (ms, default 4000, capped at 15000) — how long to let
  Maps' listing data finish loading after the page shell arrives. If a
  particular search keeps coming back with 0 real business domains, try
  bumping it (`&wait=7000`).
- The browser instance is reused across requests (only the page/context is
  recreated each time), so after the first request per container the service
  responds much faster than a fresh cold start.
