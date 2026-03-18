# Scrapers

## Baania (Bangkok houses)

Spider: `gis-server/scripts/scrapers/baania_house_spider.py`

Recommended chunked run via `make`:

```bash
cd /Users/sosokker/work/project-ku/site-select-core/gis-server
make scrape-baania-bkk START_PAGE=1 MAX_PAGES=10
```

Smoke test:

```bash
cd /Users/sosokker/work/project-ku/site-select-core/gis-server
uv run --with scrapy scrapy runspider scripts/scrapers/baania_house_spider.py \
  -a max_pages=1 -a max_details=3 -a include_raw=0 \
  -O /tmp/baania_houses_smoke.jsonl
```

Full run:

```bash
uv run --with scrapy scrapy runspider scripts/scrapers/baania_house_spider.py \
  -a include_raw=0 \
  -O data/scraped/baania_bangkok_houses.jsonl
```

## Hipflat (Bangkok house projects)

Spider: `gis-server/scripts/scrapers/hipflat_bangkok_house_spider.py`

First-time browser install (required by Playwright):

```bash
cd /Users/sosokker/work/project-ku/site-select-core/gis-server
uv run --with playwright playwright install chromium
```

Recommended chunked run via `make`:

```bash
cd /Users/sosokker/work/project-ku/site-select-core/gis-server
make playwright-install
make scrape-hipflat-bkk START_PAGE=1 MAX_PAGES=10
```

Smoke test:

```bash
uv run --with scrapy --with scrapy-playwright --with playwright \
  scrapy runspider scripts/scrapers/hipflat_bangkok_house_spider.py \
  -a start_page=1 -a max_pages=1 -a max_details=3 \
  -O /tmp/hipflat_bangkok_houses_smoke.jsonl
```

Full run:

```bash
uv run --with scrapy --with scrapy-playwright --with playwright \
  scrapy runspider scripts/scrapers/hipflat_bangkok_house_spider.py \
  -O data/scraped/hipflat_bangkok_houses.jsonl
```

## Recommended End-To-End Sequence

1. Scrape Baania chunk(s): `make scrape-baania-bkk START_PAGE=1 MAX_PAGES=10`
2. Scrape Hipflat chunk(s): `make scrape-hipflat-bkk START_PAGE=1 MAX_PAGES=10`
3. Load new JSONL files: `make load-scraped-bkk DATE_TAG=YYYYMMDD`
4. Sync images in batches: `make sync-scraped-images IMAGE_LIMIT=5000`
5. Rebuild the combined benchmark when enough new rows land: `make rebuild-combined-benchmark`
6. Build the listing-only benchmark when needed: `make build-listing-only-benchmark`

Concurrency guidance:

- Safe to run Baania and Hipflat scrapes at the same time in separate terminals
- Do not run `load-scraped-bkk` while a scrape is still writing the same output file
- Do not run multiple `sync-scraped-images` commands at the same time against the same database
- Safe pattern: run scrape jobs concurrently, then load once, then run one image-sync worker
