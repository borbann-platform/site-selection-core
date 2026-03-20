"""Materialized view refresh lifecycle for listings tile source."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from src.config.database import SessionLocal
from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ListingsTileRefreshStats:
    last_success_epoch: float = 0.0
    last_attempt_epoch: float = 0.0
    last_duration_seconds: float = 0.0
    total_success: int = 0
    total_failure: int = 0
    last_error: str = ""

    @property
    def age_seconds(self) -> float:
        if self.last_success_epoch <= 0:
            return float("inf")
        return max(0.0, time.time() - self.last_success_epoch)

    @property
    def stale(self) -> bool:
        return self.age_seconds > settings.LISTINGS_TILE_MATVIEW_STALE_SECONDS

    @property
    def last_success_iso(self) -> str:
        if self.last_success_epoch <= 0:
            return ""
        return datetime.fromtimestamp(
            self.last_success_epoch, tz=timezone.utc
        ).isoformat()


class ListingsTileRefreshManager:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = ListingsTileRefreshStats()
        self._lock = threading.Lock()
        self._refresh_interval_seconds = max(
            60, settings.LISTINGS_TILE_MATVIEW_REFRESH_SECONDS
        )
        self._ddl_lock_key = 429001
        self._refresh_lock_key = 429002

    def ensure_objects(self) -> None:
        db = SessionLocal()
        try:
            db.execute(text("SELECT pg_advisory_lock(:k)"), {"k": self._ddl_lock_key})
            exists = db.execute(
                text("SELECT to_regclass('public.mat_listings_tile_source')")
            ).scalar()
            if exists is None:
                db.execute(
                    text(
                        r"""
                    CREATE MATERIALIZED VIEW mat_listings_tile_source AS
                    WITH districts AS (
                        SELECT amphur
                        FROM (
                            SELECT DISTINCT amphur
                            FROM house_prices
                            WHERE amphur IS NOT NULL
                              AND amphur <> ''
                        ) d
                    ),
                    house_rows AS (
                        SELECT
                            ('house:' || h.id::text) AS listing_key,
                            h.id::text AS id,
                            'house_price'::text AS source_type,
                            'treasury'::text AS source,
                            h.total_price::double precision AS total_price,
                            h.building_area::double precision AS building_area,
                            h.no_of_floor::double precision AS no_of_floor,
                            h.building_age::double precision AS building_age,
                            h.building_style_desc::text AS building_style_desc,
                            h.amphur::text AS amphur,
                            h.tumbon::text AS tumbon,
                            NULL::text AS image_url,
                            NULL::text AS detail_url,
                            COALESCE(h.village, h.amphur || ' ' || COALESCE(h.building_style_desc, 'Property'))::text AS title,
                            ST_Transform(h.geometry, 3857) AS geom_3857
                        FROM house_prices h
                        WHERE h.geometry IS NOT NULL
                    ),
                    scraped_rows AS (
                        SELECT
                            ('scraped:' || s.source || ':' || s.id::text) AS listing_key,
                            s.source_listing_id::text AS id,
                            'scraped_project'::text AS source_type,
                            s.source::text AS source,
                            COALESCE(s.price_start, s.price_end)::double precision AS total_price,
                            NULL::double precision AS building_area,
                            NULL::double precision AS no_of_floor,
                            NULL::double precision AS building_age,
                            s.property_type::text AS building_style_desc,
                            s.district::text AS amphur,
                            s.subdistrict::text AS tumbon,
                            s.main_image_url::text AS image_url,
                            s.detail_url::text AS detail_url,
                            COALESCE(s.title, s.title_en, s.title_th)::text AS title,
                            ST_Transform(s.geometry, 3857) AS geom_3857
                        FROM scraped_listings s
                        WHERE s.geometry IS NOT NULL
                    ),
                    market_rows AS (
                        SELECT
                            ('market:' || r.id::text) AS listing_key,
                            r.id::text AS id,
                            'market_listing'::text AS source_type,
                            'baania'::text AS source,
                            COALESCE(NULLIF(regexp_replace(r.price, '[^0-9.]', '', 'g'), '')::double precision, 0) AS total_price,
                            NULLIF(regexp_replace(r.usable_area_sqm, '[^0-9.]', '', 'g'), '')::double precision AS building_area,
                            NULLIF(regexp_replace(r.floors, '[^0-9.]', '', 'g'), '')::double precision AS no_of_floor,
                            NULL::double precision AS building_age,
                            r.property_type::text AS building_style_desc,
                            district_lookup.amphur::text AS amphur,
                            NULL::text AS tumbon,
                            substring(r.images from '(https?://[^,\s\]"\'']+)')::text AS image_url,
                            NULL::text AS detail_url,
                            r.title::text AS title,
                            ST_Transform(r.geometry, 3857) AS geom_3857
                        FROM real_estate_listings r
                        LEFT JOIN LATERAL (
                            SELECT d.amphur
                            FROM districts d
                            WHERE r.location ILIKE ('%' || d.amphur || '%')
                            ORDER BY length(d.amphur) DESC
                            LIMIT 1
                        ) district_lookup ON TRUE
                        WHERE r.geometry IS NOT NULL
                    ),
                    condo_rows AS (
                        SELECT
                            ('condo:' || c.id::text) AS listing_key,
                            c.id::text AS id,
                            'condo_project'::text AS source_type,
                            'hipflat'::text AS source,
                            COALESCE(NULLIF(regexp_replace(c.price_sale, '[^0-9.]', '', 'g'), '')::double precision, 0) AS total_price,
                            NULL::double precision AS building_area,
                            NULL::double precision AS no_of_floor,
                            NULL::double precision AS building_age,
                            'Condominium'::text AS building_style_desc,
                            district_lookup.amphur::text AS amphur,
                            NULL::text AS tumbon,
                            NULL::text AS image_url,
                            c.project_base_url::text AS detail_url,
                            c.name::text AS title,
                            ST_Transform(c.geometry, 3857) AS geom_3857
                        FROM condo_projects c
                        LEFT JOIN LATERAL (
                            SELECT d.amphur
                            FROM districts d
                            WHERE c.location ILIKE ('%' || d.amphur || '%')
                            ORDER BY length(d.amphur) DESC
                            LIMIT 1
                        ) district_lookup ON TRUE
                        WHERE c.geometry IS NOT NULL
                    )
                    SELECT * FROM house_rows
                    UNION ALL
                    SELECT * FROM scraped_rows
                    UNION ALL
                    SELECT * FROM market_rows
                    UNION ALL
                    SELECT * FROM condo_rows;
                    """
                    )
                )
            db.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_mat_listings_tile_source_listing_key ON mat_listings_tile_source (listing_key)"
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_mat_listings_tile_source_geom_3857 ON mat_listings_tile_source USING GIST (geom_3857)"
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_mat_listings_tile_source_filters ON mat_listings_tile_source (source_type, amphur, building_style_desc)"
                )
            )
            db.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_mat_listings_tile_source_price_area ON mat_listings_tile_source (total_price, building_area)"
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("listings_tile_matview_ensure_failed")
            raise
        finally:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": self._ddl_lock_key}
                )
                db.commit()
            except Exception:
                db.rollback()
            db.close()

    def _do_refresh(self, *, concurrent: bool) -> None:
        start = time.perf_counter()
        now_epoch = time.time()
        with self._lock:
            self._stats.last_attempt_epoch = now_epoch

        db = SessionLocal()
        try:
            lock_acquired = db.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": self._refresh_lock_key},
            ).scalar()
            if not lock_acquired:
                logger.info("listings_tile_refresh_skipped reason=lock_busy")
                return

            if concurrent:
                db.execute(
                    text(
                        "REFRESH MATERIALIZED VIEW CONCURRENTLY mat_listings_tile_source"
                    )
                )
            else:
                db.execute(text("REFRESH MATERIALIZED VIEW mat_listings_tile_source"))
            db.commit()
        except Exception as exc:
            db.rollback()
            duration = time.perf_counter() - start
            with self._lock:
                self._stats.total_failure += 1
                self._stats.last_duration_seconds = duration
                self._stats.last_error = str(exc)
            logger.exception("listings_tile_refresh_failed concurrent=%s", concurrent)
        else:
            duration = time.perf_counter() - start
            with self._lock:
                self._stats.total_success += 1
                self._stats.last_duration_seconds = duration
                self._stats.last_success_epoch = now_epoch
                self._stats.last_error = ""
            logger.info(
                "listings_tile_refresh_success concurrent=%s duration_seconds=%.3f",
                concurrent,
                duration,
            )
        finally:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:k)"),
                    {"k": self._refresh_lock_key},
                )
                db.commit()
            except Exception:
                db.rollback()
            db.close()

    def refresh_now(self, *, concurrent: bool = True) -> None:
        self._do_refresh(concurrent=concurrent)

    def _refresh_loop(self) -> None:
        while not self._stop_event.wait(self._refresh_interval_seconds):
            self._do_refresh(concurrent=True)

    def start(self) -> None:
        if self._thread is not None:
            return
        self.ensure_objects()
        self.refresh_now(concurrent=False)
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="listings-tile-refresh",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def get_stats(self) -> ListingsTileRefreshStats:
        with self._lock:
            return ListingsTileRefreshStats(
                last_success_epoch=self._stats.last_success_epoch,
                last_attempt_epoch=self._stats.last_attempt_epoch,
                last_duration_seconds=self._stats.last_duration_seconds,
                total_success=self._stats.total_success,
                total_failure=self._stats.total_failure,
                last_error=self._stats.last_error,
            )


listings_tile_refresh_manager = ListingsTileRefreshManager()
