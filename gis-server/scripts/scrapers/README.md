# Scrapers

## Baania (Bangkok houses)

Spider: `gis-server/scripts/scrapers/baania_house_spider.py`

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
