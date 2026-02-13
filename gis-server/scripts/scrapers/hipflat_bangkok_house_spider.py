from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import scrapy
from scrapy.http import Request, Response

try:
    from scrapy_playwright.page import PageMethod
except Exception:  # pragma: no cover - runtime dependency
    PageMethod = None  # type: ignore[assignment]


class HipflatBangkokHouseSpider(scrapy.Spider):
    name = "hipflat_bangkok_house"
    allowed_domains = ["hipflat.co.th", "www.hipflat.co.th"]

    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 120_000,
        "PLAYWRIGHT_MAX_CONTEXTS": 1,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 0.6,
        "RETRY_TIMES": 2,
        "DOWNLOAD_TIMEOUT": 180,
        "AUTOTHROTTLE_ENABLED": False,
    }

    START_URL = "https://www.hipflat.co.th/en/thailand-projects/house/bangkok-bm?page=1"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    CHALLENGE_MARKER = "just a moment"
    HIPFLAT_IMAGE_HINTS = ("img.hipcdn.com", "projects-manager-images", "hipflat")

    def __init__(
        self,
        start_page: str = "1",
        end_page: str | None = None,
        max_pages: str | None = None,
        max_details: str | None = None,
        max_cf_retries: str = "2",
        search_wait_ms: str = "30000",
        detail_wait_ms: str = "30000",
        challenge_wait_ms: str = "45000",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.start_page = max(int(start_page), 1)
        self.max_pages = int(max_pages) if max_pages else None
        self.max_details = int(max_details) if max_details else None
        self.max_cf_retries = max(int(max_cf_retries), 0)
        self.search_wait_ms = max(int(search_wait_ms), 1_000)
        self.detail_wait_ms = max(int(detail_wait_ms), 1_000)
        self.challenge_wait_ms = max(int(challenge_wait_ms), self.detail_wait_ms)

        requested_end_page = int(end_page) if end_page else None
        if requested_end_page is not None:
            self.end_page = requested_end_page
        elif self.max_pages is not None:
            self.end_page = self.start_page + self.max_pages - 1
        else:
            self.end_page = None

        self._seen_project_urls: set[str] = set()
        self._scheduled_details = 0

    async def start(self):
        if PageMethod is None:
            raise RuntimeError(
                "scrapy-playwright is required. Run with: "
                "uv run --with scrapy --with scrapy-playwright --with playwright scrapy runspider ..."
            )
        start_url = self._set_page(self.START_URL, self.start_page)
        yield scrapy.Request(
            start_url,
            callback=self.parse_search_page,
            headers={"User-Agent": self.USER_AGENT},
            meta=self._playwright_meta(detail=False),
            dont_filter=True,
        )

    def parse_search_page(self, response: Response):
        if self._is_challenge(response):
            retry = self._retry_count(response)
            if retry <= self.max_cf_retries:
                self.logger.warning("Cloudflare challenge on search page. Retry=%s url=%s", retry, response.url)
                yield self._retry_request(response, self.parse_search_page, detail=False)
            else:
                self.logger.warning("Skipping search page after retries: %s", response.url)
            return

        page_no = self._extract_page_no(response.url)
        project_cards = response.css("div.projects-list div.project-snippet")
        if not project_cards:
            self.logger.warning("No project cards found on %s", response.url)
            return

        total_results = self._extract_total_results(response)
        per_page = max(len(project_cards), 1)
        total_pages = math.ceil(total_results / per_page) if total_results else page_no

        self.logger.info(
            "Loaded Hipflat page=%s cards=%s total_results=%s total_pages=%s",
            page_no,
            len(project_cards),
            total_results,
            total_pages,
        )

        for card in project_cards:
            listing = self._extract_listing_card(card)
            if not listing:
                continue

            property_type = (listing.get("property_type") or "").lower()
            if "house" not in property_type:
                continue

            project_url = listing["project_url"]
            if project_url in self._seen_project_urls:
                continue
            if self.max_details is not None and self._scheduled_details >= self.max_details:
                break

            self._seen_project_urls.add(project_url)
            self._scheduled_details += 1

            yield response.follow(
                project_url,
                callback=self.parse_project_page,
                headers={"User-Agent": self.USER_AGENT},
                meta={
                    **self._playwright_meta(detail=True),
                    "listing": listing,
                    "search_page": page_no,
                },
                dont_filter=True,
            )

        if self.max_details is not None and self._scheduled_details >= self.max_details:
            self.logger.info("Reached max_details=%s; stopping pagination.", self.max_details)
            return

        next_page = page_no + 1
        if next_page > total_pages:
            return
        if self.end_page is not None and next_page > self.end_page:
            return

        next_url = self._set_page(response.url, next_page)
        yield scrapy.Request(
            next_url,
            callback=self.parse_search_page,
            headers={"User-Agent": self.USER_AGENT},
            meta=self._playwright_meta(detail=False),
            dont_filter=True,
        )

    def parse_project_page(self, response: Response):
        if self._is_challenge(response):
            retry = self._retry_count(response)
            if retry <= self.max_cf_retries:
                self.logger.warning("Cloudflare challenge on detail page. Retry=%s url=%s", retry, response.url)
                yield self._retry_request(response, self.parse_project_page, detail=True)
            else:
                self.logger.warning("Skipping detail page after retries: %s", response.url)
            return

        listing = response.meta.get("listing") or {}
        search_page = response.meta.get("search_page")

        faq_data: list[dict[str, Any]] = []
        breadcrumb_data: list[str] = []
        apartment_data: dict[str, Any] = {}

        for raw in response.css("script[type='application/ld+json']::text").getall():
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type")
                if item_type == "ApartmentComplex":
                    apartment_data = item
                elif item_type == "FAQPage":
                    faq_data = self._extract_faq(item)
                elif item_type == "BreadcrumbList":
                    breadcrumb_data = self._extract_breadcrumbs(item)

        if apartment_data:
            region = (
                ((apartment_data.get("address") or {}).get("addressRegion") or "").strip().lower()
            )
            if region and "bangkok" not in region:
                return

        image_urls = self._extract_image_urls(response, apartment_data)
        amenities = [
            feature.get("name")
            for feature in apartment_data.get("amenityFeature", [])
            if isinstance(feature, dict) and feature.get("name")
        ]

        address = apartment_data.get("address") or {}
        geo = apartment_data.get("geo") or {}

        item = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "search_page": search_page,
            "source": "hipflat",
            "source_list_url": self._set_page(self.START_URL, int(search_page or 1)),
            "project_url": response.url,
            "project_id": self._extract_project_id(response.url),
            "project_name": apartment_data.get("name") or listing.get("project_name"),
            "listing_title": listing.get("project_name"),
            "property_type": listing.get("property_type"),
            "sale_price": listing.get("sale_price"),
            "rent_price": listing.get("rent_price"),
            "bedrooms": listing.get("bedrooms"),
            "bathrooms": listing.get("bathrooms"),
            "area_m2": listing.get("area_m2"),
            "listing_address": listing.get("listing_address"),
            "listing_summary": listing.get("summary"),
            "description": apartment_data.get("description"),
            "available_units": self._extract_available_units(apartment_data),
            "address": {
                "street": address.get("streetAddress"),
                "district_or_locality": address.get("addressLocality"),
                "region": address.get("addressRegion"),
                "postal_code": address.get("postalCode"),
                "country_code": ((address.get("addressCountry") or {}).get("name")),
            },
            "location": {
                "lat": geo.get("latitude"),
                "lon": geo.get("longitude"),
            },
            "amenities": amenities,
            "faq": faq_data,
            "breadcrumbs": breadcrumb_data,
            "main_image_url": apartment_data.get("image"),
            "image_urls": image_urls,
        }
        yield item

    def _playwright_meta(self, detail: bool, is_retry: bool = False) -> dict[str, Any]:
        assert PageMethod is not None
        wait_ms = self.detail_wait_ms if detail else self.search_wait_ms
        if is_retry:
            wait_ms = self.challenge_wait_ms
        return {
            "playwright": True,
            "playwright_context": "default",
            "playwright_page_methods": [
                PageMethod("wait_for_load_state", "domcontentloaded"),
                PageMethod("wait_for_timeout", wait_ms),
            ],
        }

    def _retry_count(self, response: Response) -> int:
        return int(response.meta.get("cf_retry", 0)) + 1

    def _retry_request(self, response: Response, callback, detail: bool) -> Request:
        new_meta = {k: v for k, v in response.meta.items() if not str(k).startswith("playwright")}
        new_meta["cf_retry"] = self._retry_count(response)
        new_meta.update(self._playwright_meta(detail=detail, is_retry=True))
        return response.request.replace(
            callback=callback,
            dont_filter=True,
            meta=new_meta,
            headers={"User-Agent": self.USER_AGENT},
        )

    def _is_challenge(self, response: Response) -> bool:
        title = (response.css("title::text").get() or "").strip().lower()
        if self.CHALLENGE_MARKER in title:
            return True
        body_head = response.text[:4000].lower()
        return "enable javascript and cookies to continue" in body_head

    def _extract_page_no(self, url: str) -> int:
        query = parse_qs(urlparse(url).query)
        try:
            return max(int((query.get("page") or ["1"])[0]), 1)
        except ValueError:
            return 1

    def _set_page(self, url: str, page: int) -> str:
        parts = urlparse(url)
        query = parse_qs(parts.query, keep_blank_values=True)
        query["page"] = [str(page)]
        return urlunparse(parts._replace(query=urlencode(query, doseq=True)))

    def _extract_total_results(self, response: Response) -> int:
        summary = (response.css("p.pagination-summary::text").get() or "").strip()
        match = re.search(r"of\s+([\d,]+)\s+results", summary, re.IGNORECASE)
        if not match:
            return 0
        return int(match.group(1).replace(",", ""))

    def _extract_listing_card(self, card: scrapy.Selector) -> dict[str, Any] | None:
        href = card.css("a::attr(href)").get()
        title = (card.css("a::attr(title)").get() or "").strip()
        if not href:
            return None

        prices = [
            " ".join(text.split())
            for text in card.css("p.project-snippet-price::text").getall()
            if text and text.strip()
        ]
        sale_price = next((line for line in prices if line.lower().startswith("sale price")), None)
        rent_price = next((line for line in prices if line.lower().startswith("rent price")), None)

        info_map: dict[str, str] = {}
        for li in card.css("ul.project-snippet-info li"):
            key = ((li.css("img::attr(alt)").get() or "").strip().lower()) or "unknown"
            value = " ".join(v.strip() for v in li.css("::text").getall() if v.strip())
            info_map[key] = value

        summary = " ".join(
            line.strip()
            for line in card.css("p.project-snippet-description::text").getall()
            if line and line.strip()
        )

        return {
            "project_url": href,
            "project_name": title,
            "sale_price": sale_price,
            "rent_price": rent_price,
            "listing_address": " ".join(
                t.strip() for t in card.css("p.project-snippet-address::text").getall() if t.strip()
            ),
            "summary": summary,
            "bedrooms": info_map.get("beds"),
            "bathrooms": info_map.get("baths"),
            "area_m2": info_map.get("space"),
            "property_type": info_map.get("property type"),
        }

    def _extract_project_id(self, url: str) -> str | None:
        slug = url.rstrip("/").split("/")[-1]
        if not slug:
            return None
        return slug

    def _extract_available_units(self, apartment_data: dict[str, Any]) -> int | None:
        value = (apartment_data.get("numberOfAvailableAccommodationUnits") or {}).get("value")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _extract_faq(self, faq_obj: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for question in faq_obj.get("mainEntity", []):
            if not isinstance(question, dict):
                continue
            answer = question.get("acceptedAnswer") or {}
            items.append(
                {
                    "question": question.get("name"),
                    "answer": answer.get("text"),
                }
            )
        return items

    def _extract_breadcrumbs(self, breadcrumb_obj: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for item in breadcrumb_obj.get("itemListElement", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name:
                names.append(str(name))
        return names

    def _extract_image_urls(self, response: Response, apartment_data: dict[str, Any]) -> list[str]:
        urls: set[str] = set()

        image_field = apartment_data.get("image")
        if isinstance(image_field, str) and image_field.startswith("http"):
            urls.add(image_field)
        elif isinstance(image_field, list):
            for value in image_field:
                if isinstance(value, str) and value.startswith("http"):
                    urls.add(value)

        og_image = response.css("meta[property='og:image']::attr(content)").get()
        if og_image and og_image.startswith("http"):
            urls.add(og_image)

        for src in response.css("img::attr(src)").getall():
            if not src or not src.startswith("http"):
                continue
            if any(hint in src for hint in self.HIPFLAT_IMAGE_HINTS):
                urls.add(src)

        return sorted(urls)
