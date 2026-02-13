from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import scrapy
from scrapy.http import Response


class BaaniaHouseSpider(scrapy.Spider):
    name = "baania_house"
    allowed_domains = ["baania.com", "www.baania.com"]

    custom_settings = {
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.35,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    SEARCH_PATH = "/s/%E0%B8%97%E0%B8%B1%E0%B9%89%E0%B8%87%E0%B8%AB%E0%B8%A1%E0%B8%94/project"
    HOUSE_KEYWORDS_EN = ("house", "townhome", "town house", "twin")
    HOUSE_KEYWORDS_TH = ("บ้าน", "ทาวน์โฮม", "ทาวน์เฮ้าส์", "บ้านแฝด")
    IMAGE_PATH_HINTS = ("image", "thumbnail", "photo", "webp", "gallery")
    IMAGE_URL_PATTERN = re.compile(r"\.(?:jpg|jpeg|png|webp|gif)(?:$|[?#])", re.IGNORECASE)

    def __init__(
        self,
        province_id: str = "3781",
        sort_updated: str = "desc",
        start_page: str = "1",
        end_page: str | None = None,
        max_pages: str | None = None,
        max_details: str | None = None,
        include_raw: str = "1",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.province_id = str(province_id)
        self.sort_updated = sort_updated
        self.start_page = max(int(start_page), 1)
        requested_end_page = int(end_page) if end_page else None
        self.max_pages = int(max_pages) if max_pages else None
        if requested_end_page is not None:
            self.end_page = requested_end_page
        elif self.max_pages is not None:
            if self.start_page > 1:
                self.end_page = self.start_page + self.max_pages - 1
            else:
                self.end_page = self.max_pages
        else:
            self.end_page = None
        self.max_details = int(max_details) if max_details else None
        self.include_raw = str(include_raw).strip().lower() not in {"0", "false", "no"}
        self._seen_detail_urls: set[str] = set()
        self._scheduled_details = 0

    async def start(self):
        yield scrapy.Request(
            url=self._build_search_url(page=self.start_page),
            callback=self.parse_search_page,
            headers=self._default_headers(),
            dont_filter=True,
        )

    def parse_search_page(self, response: Response):
        payload = self._extract_next_data(response)
        if not payload:
            self.logger.warning("Missing __NEXT_DATA__ on search page: %s", response.url)
            return

        hits_data = (
            payload.get("props", {})
            .get("pageProps", {})
            .get("defaultData", {})
            .get("hits", {})
        )
        hits = hits_data.get("hits") or []
        total = int((hits_data.get("total") or {}).get("value") or 0)
        page = self._extract_page_number(response.url)
        per_page = max(len(hits), 1)
        total_pages = math.ceil(total / per_page) if total else page

        self.logger.info(
            "Search page=%s loaded %s listings (total=%s, total_pages=%s)",
            page,
            len(hits),
            total,
            total_pages,
        )

        for hit in hits:
            source = hit.get("_source") or {}
            view_data = source.get("view_data") or {}
            if not self._is_house_listing(view_data):
                continue

            detail_url = self._resolve_detail_url(response.url, view_data.get("url"))
            if not detail_url or detail_url in self._seen_detail_urls:
                continue
            if self.max_details is not None and self._scheduled_details >= self.max_details:
                break

            self._seen_detail_urls.add(detail_url)
            self._scheduled_details += 1

            yield response.follow(
                detail_url,
                callback=self.parse_project_page,
                headers=self._default_headers(),
                meta={
                    "search_page": page,
                    "search_hit_id": hit.get("_id"),
                    "search_score": hit.get("_score"),
                    "search_source": source,
                },
            )

        if self.max_details is not None and self._scheduled_details >= self.max_details:
            self.logger.info("Reached max_details=%s. Stopping pagination.", self.max_details)
            return

        next_page = page + 1
        if self.end_page is not None and next_page > self.end_page:
            return
        if next_page > total_pages:
            return

        yield scrapy.Request(
            url=self._build_search_url(page=next_page),
            callback=self.parse_search_page,
            headers=self._default_headers(),
        )

    def parse_project_page(self, response: Response):
        payload = self._extract_next_data(response)
        if not payload:
            self.logger.warning("Missing __NEXT_DATA__ on detail page: %s", response.url)
            return

        project_root = payload.get("props", {}).get("pageProps", {}).get("project", {})
        project_data = project_root.get("data") or {}
        if not project_data:
            self.logger.warning("Project payload missing on detail page: %s", response.url)
            return

        search_source = response.meta.get("search_source") or {}
        search_view_data = search_source.get("view_data") or {}

        address = project_data.get("address") or {}
        info = project_data.get("info") or {}
        general = project_data.get("general") or {}
        geopoint = project_root.get("geopoint") or {}

        coordinates = geopoint.get("coordinates") if isinstance(geopoint, dict) else None
        lon = coordinates[0] if isinstance(coordinates, list) and len(coordinates) > 1 else None
        lat = coordinates[1] if isinstance(coordinates, list) and len(coordinates) > 1 else None

        image_urls = sorted(
            self._collect_image_urls(project_data) | self._collect_image_urls(search_view_data)
        )

        item = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "search_page": response.meta.get("search_page"),
            "search_hit_id": response.meta.get("search_hit_id"),
            "search_score": response.meta.get("search_score"),
            "listing_id": project_root.get("keyId") or project_data.get("id"),
            "code": info.get("code") or search_view_data.get("code"),
            "title_th": info.get("title_th") or self._nested_get(search_view_data, "title", "th"),
            "title_en": info.get("title_en") or self._nested_get(search_view_data, "title", "en"),
            "detail_url": response.url,
            "source_url": self._resolve_source_url(search_view_data.get("url")),
            "property_types": self._normalize_property_types(
                project_data.get("property_type"), fallback=search_view_data.get("property_type")
            ),
            "province_id": address.get("province_id"),
            "province_th": address.get("province_th"),
            "province_en": address.get("province_en"),
            "district_id": address.get("district_id"),
            "district_th": address.get("district_th"),
            "district_en": address.get("district_en"),
            "subdistrict_id": address.get("subdistrict_id"),
            "subdistrict_th": address.get("subdistrict_th"),
            "subdistrict_en": address.get("subdistrict_en"),
            "status": general.get("status"),
            "main_image_url": self._pick_main_image(project_data, search_view_data),
            "image_urls": image_urls,
            "location": {"lat": lat, "lon": lon},
            "developer": project_data.get("developer"),
            "general": general,
            "detail": project_data.get("detail"),
            "financial": project_data.get("financial"),
            "facility": project_data.get("facility"),
            "progress": project_data.get("progress"),
            "unit_types": project_data.get("unittype"),
            "contact": {
                "website": project_data.get("website"),
                "facebook": project_data.get("facebook"),
                "line": project_data.get("line"),
                "email": project_data.get("email"),
                "selloffice": project_data.get("selloffice"),
            },
            "video": project_data.get("video"),
        }

        if self.include_raw:
            item["raw_project_data"] = project_data
            item["raw_search_source"] = search_source

        yield item

    def _build_search_url(self, page: int) -> str:
        query = urlencode(
            {"province": self.province_id, "sort.updated": self.sort_updated, "page": page}
        )
        return f"https://www.baania.com{self.SEARCH_PATH}?{query}"

    def _extract_page_number(self, url: str) -> int:
        query = parse_qs(urlparse(url).query)
        value = query.get("page", ["1"])[0]
        try:
            return max(int(value), 1)
        except ValueError:
            return 1

    def _default_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

    def _extract_next_data(self, response: Response) -> dict[str, Any] | None:
        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                response.text,
                re.DOTALL,
            )
            raw = match.group(1) if match else None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.logger.warning("Cannot decode __NEXT_DATA__ JSON for %s", response.url)
            return None
        if isinstance(data, dict):
            return data
        return None

    def _is_house_listing(self, view_data: dict[str, Any]) -> bool:
        property_type = view_data.get("property_type")
        texts: list[str] = []

        if isinstance(property_type, dict):
            texts.extend(
                str(property_type.get(key, "")).strip()
                for key in ("th", "en", "title_th", "title_en")
            )
        elif isinstance(property_type, list):
            for entry in property_type:
                if isinstance(entry, dict):
                    texts.extend(
                        str(entry.get(key, "")).strip()
                        for key in ("th", "en", "title_th", "title_en")
                    )
                elif entry:
                    texts.append(str(entry).strip())
        elif property_type:
            texts.append(str(property_type).strip())

        title = self._nested_get(view_data, "title", "th") or ""
        if title:
            texts.append(title)

        joined = " ".join(part for part in texts if part).lower()
        if not joined:
            return False

        has_house_keyword = any(keyword in joined for keyword in self.HOUSE_KEYWORDS_EN) or any(
            keyword in joined for keyword in self.HOUSE_KEYWORDS_TH
        )
        return has_house_keyword

    def _resolve_detail_url(self, base_url: str, url_data: Any) -> str | None:
        if not isinstance(url_data, dict):
            return None
        alias_url = url_data.get("alias_url")
        source_url = url_data.get("source_url")
        if source_url:
            normalized = str(source_url)
            if not normalized.startswith("/"):
                normalized = f"/{normalized}"
            return urljoin(base_url, normalized)
        if alias_url:
            return urljoin(base_url, str(alias_url))
        return None

    def _resolve_source_url(self, url_data: Any) -> str | None:
        if not isinstance(url_data, dict):
            return None
        source_url = url_data.get("source_url")
        if not source_url:
            return None
        normalized = str(source_url)
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return f"https://www.baania.com{normalized}"

    def _normalize_property_types(self, value: Any, fallback: Any = None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for entry in self._iter_property_types(value):
            if entry not in normalized:
                normalized.append(entry)
        if normalized:
            return normalized
        for entry in self._iter_property_types(fallback):
            if entry not in normalized:
                normalized.append(entry)
        return normalized

    def _iter_property_types(self, value: Any):
        if isinstance(value, dict):
            yield {
                "id": value.get("id"),
                "th": value.get("title_th") or value.get("th"),
                "en": value.get("title_en") or value.get("en"),
            }
            return
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    yield {
                        "id": entry.get("id"),
                        "th": entry.get("title_th") or entry.get("th"),
                        "en": entry.get("title_en") or entry.get("en"),
                    }
                elif entry:
                    yield {"id": None, "th": None, "en": str(entry)}
            return
        if value:
            yield {"id": None, "th": None, "en": str(value)}

    def _collect_image_urls(self, node: Any, path: tuple[str, ...] = ()) -> set[str]:
        urls: set[str] = set()
        if isinstance(node, dict):
            for key, value in node.items():
                urls |= self._collect_image_urls(value, (*path, str(key)))
            return urls
        if isinstance(node, list):
            for item in node:
                urls |= self._collect_image_urls(item, path)
            return urls
        if not isinstance(node, str):
            return urls

        value = node.strip()
        if not value.startswith("http"):
            return urls

        path_key = ".".join(path).lower()
        if any(hint in path_key for hint in self.IMAGE_PATH_HINTS) or self.IMAGE_URL_PATTERN.search(
            value
        ):
            urls.add(value)
        return urls

    def _pick_main_image(self, project_data: dict[str, Any], search_view_data: dict[str, Any]) -> str | None:
        images = project_data.get("images") if isinstance(project_data, dict) else None
        if isinstance(images, dict):
            main = images.get("main")
            if isinstance(main, dict):
                url = main.get("url")
                if isinstance(url, str) and url:
                    return url
        search_image = search_view_data.get("image") if isinstance(search_view_data, dict) else None
        if isinstance(search_image, dict):
            url = search_image.get("url")
            if isinstance(url, str) and url:
                return url
        return None

    def _nested_get(self, node: dict[str, Any], *keys: str) -> Any:
        current: Any = node
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current
