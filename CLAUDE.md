# Bestimate - Zillow Property Data Scraper

## What This Project Does

Scrapes Zillow property data at scale: zestimate, price, beds, baths, sqft, lot size, year built, property type. Replaces an external vendor that charges $800/month.

## How It Works (The Discovery)

Zillow uses PerimeterX (PX) anti-bot protection that blocks standard HTTP requests, headless browsers, and even curl. After extensive testing, we found a bypass:

### The Bridge API Cookie Trick

```
Step 1: GET https://www.zillow.com/bridge/api/v1/property/get
        -> Returns HTTP 200 with session cookies (zguid, zgsession)
        -> This endpoint is NOT protected by PerimeterX

Step 2: GET https://www.zillowstatic.com/autocomplete/v3/suggestions?q={address}+{zip}
        -> Returns zpid (Zillow Property ID) from address
        -> Also NOT protected by PerimeterX
        -> IMPORTANT: Search by address + zip only, NOT city
          (cities in input data often don't match Zillow's city names)

Step 3: GET https://www.zillow.com/homedetails/{slug}/{zpid}_zpid/
        -> With cookies from Step 1, PX does not challenge
        -> Parse __NEXT_DATA__ JSON embedded in HTML for all property fields
```

### Key Findings

- Bridge API cookies are NOT tied to IP address (can obtain via proxy, use from anywhere)
- Autocomplete works without any cookies or proxy
- PacketStream supports sticky sessions: append `_session-{id}` to password
- `curl_cffi` with `impersonate="chrome124"` provides real Chrome TLS fingerprint
- Zillow's `__NEXT_DATA__` is at byte position 89.5% of HTML (1.7MB into a 1.9MB page)
- Compressed transfer per property: ~300KB through proxy

## Performance (Tested April 2, 2026)

### Test: 1,270 Florida Properties, 50 Workers

| Metric              | Result          |
|---------------------|-----------------|
| Success rate        | 95% (1,205/1,270) |
| First pass          | 813 OK in ~14 min |
| After retry round 1 | 1,120 OK        |
| After retry round 2 | 1,205 OK        |
| Total time          | ~34 min          |
| Speed               | ~100/min (first pass), ~36/min (with retries) |
| Proxy cost          | $0.39            |
| Cost per property   | $0.00031         |

### Speed by Worker Count (extrapolated from tests)

| Workers | Speed     | 1M properties in |
|---------|-----------|-------------------|
| 20      | ~55/min   | ~12 hours         |
| 50      | ~100/min  | ~7 hours          |
| 100     | ~200/min  | ~3.5 hours        |
| 200     | ~400/min  | ~1.7 hours        |

## Cost Breakdown

### Proxy (PacketStream at $1/GB)

Each property uses ~300KB compressed through proxy (bridge cookies + property page).

| Volume  | Proxy Cost | + VPS $32/mo | Total     |
|---------|------------|--------------|-----------|
| 10K     | $3         | $35          | $35       |
| 100K    | $31        | $63          | $63       |
| 1M      | $307       | $339         | $339      |
| 10M     | $3,071     | $3,103       | $3,103    |

### Zero-Proxy Option (untested at scale)

Bridge cookies are not IP-bound. If scraping from VPS without proxy works:
- VPS with 20TB bandwidth: $32/month flat
- Proxy only for cookie refresh: ~$1/month
- **Total: ~$33/month regardless of volume**

Risk: Datacenter IPs may get higher PX block rates.

### Current PacketStream Balance

- Started with: $50
- Used so far: ~$0.85 (all testing + runs)
- Remaining: ~$49.15 (~160K more properties)

## How to Run

### Prerequisites
- Python 3.12+
- PacketStream account with credentials

### Setup
```bash
git clone https://github.com/camiloricoe/bestimate.git
cd bestimate
pip install -e .
cp .env.example .env
# Edit .env with PacketStream credentials
```

### Run a Batch (Parallel)
```bash
# From Excel (preserves PropertyId, APN columns)
python scripts/batch_parallel.py "input.xlsx" -o results.csv -w 50

# With options
python scripts/batch_parallel.py input.csv \
  -o results.csv \
  --workers 50 \      # parallel workers
  --delay 0.8 \       # seconds between requests per worker
  --skip 100 \        # skip first N rows
  --limit 500 \       # process only N rows
  --max-retries 2     # retry rounds for blocked properties
```

### Input Format

Excel or CSV with columns:
- `Property Address` (or `address`)
- `Property Zip` (or `zip`, `zipcode`)
- `CITY` (or `city`) - used for detail URL slug, not for search
- `STATE` (or `state`)
- Optional: `PropertyId`, `APN` - preserved in output

### Output Format

CSV with all original columns plus:
- `zpid` - Zillow Property ID
- `zestimate` - Zillow's estimated value
- `price` - Listed/sale price
- `beds`, `baths`, `sqft` - Property details
- `lot_size_sqft` - Lot size in square feet
- `year_built` - Construction year
- `property_type` - SINGLE_FAMILY, TOWNHOUSE, APARTMENT, etc.
- `zillow_status` - ok, not_found, blocked, blocked_final

## Architecture

```
scripts/
  batch_parallel.py    <- Main entry point (parallel workers + retry)
  batch_scrape.py      <- Sequential version (simpler, for testing)

src/scraper/
  client.py            <- ZillowScraper class (bridge cookies + sticky sessions)
  parser.py            <- Parse __NEXT_DATA__ from Zillow HTML
  search.py            <- Build Zillow search URLs
  detail.py            <- Build Zillow detail URLs

src/anti_detect/
  headers.py           <- Realistic Chrome headers
  timing.py            <- Delays, backoff, circuit breaker
  cookies.py           <- Cookie session management
  px_solver.py         <- Playwright PX solver (fallback, not used in main flow)

src/proxy/
  manager.py           <- Proxy rotation + health tracking
  provider.py          <- PacketStream configuration

src/api/               <- FastAPI monitoring (prepared, not deployed yet)
src/worker/            <- Celery tasks (prepared, not deployed yet)
src/db/                <- SQLAlchemy models (prepared, not deployed yet)
monitoring/            <- Grafana + Prometheus configs
```

## What Didn't Work (Lessons Learned)

1. **curl_cffi direct to Zillow** - PX blocks immediately (403)
2. **Playwright headless** - PX detects headless Chrome fingerprint
3. **Playwright headed + press-and-hold** - PX detects automated mouse
4. **PX cookie transfer (Playwright -> curl_cffi)** - Cookies tied to browser fingerprint
5. **Bright Data Web Unlocker** - Blocks Zillow due to robots.txt compliance
6. **Zillow GraphQL/search APIs** - All PX-protected
7. **Autocomplete with city name** - City mismatch causes 39% miss rate (fixed by removing city)

## What DID Work

1. **Bridge API** (`/bridge/api/v1/property/get`) - Returns cookies without PX
2. **Autocomplete** (`zillowstatic.com`) - Address to zpid without PX
3. **curl_cffi with bridge cookies** - Full property pages, no PX challenge
4. **PacketStream sticky sessions** - `_session-{id}` in password field
5. **Parallel workers with ThreadPoolExecutor** - Linear scaling
6. **Retry rounds** - Recovers ~65% of initially blocked properties

## Proxy Configuration

PacketStream rotating residential proxy:
```
Host: proxy.packetstream.io
Port: 31112
User: {username}
Pass: {password}

# For sticky sessions (same IP ~10 min):
Pass: {password}_session-{random_id}
```

## Failure Modes

| Issue | Rate | Solution |
|-------|------|----------|
| Autocomplete miss (address not in Zillow) | ~2-5% | These properties genuinely don't exist in Zillow |
| PX blocks on property page | ~35% first pass | Retry with new sticky session (new IP) |
| PX blocks after retries | ~5% final | More retry rounds or longer delays |
| Proxy connection error | Rare | Auto-retry with new session |
| Bridge API returns 403 | ~30% of attempts | Retry until 200 (usually 1-3 attempts) |
