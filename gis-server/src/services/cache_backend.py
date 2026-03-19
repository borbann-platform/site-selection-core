"""Cache backend abstraction supporting memory and Redis backends."""

from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from time import perf_counter, time

import redis

from src.config.settings import settings
from src.services.observability import cache_backend_metrics

logger = logging.getLogger(__name__)


class CacheBackendError(RuntimeError):
    pass


class CacheBackend:
    def get_bytes(self, cache_name: str, key: str) -> bytes | None:
        raise NotImplementedError

    def set_bytes(
        self, cache_name: str, key: str, value: bytes, ttl_seconds: int
    ) -> None:
        raise NotImplementedError

    def clear_namespace(self, cache_name: str) -> int:
        raise NotImplementedError

    def namespace_size(self, cache_name: str) -> int:
        raise NotImplementedError

    @property
    def backend_name(self) -> str:
        raise NotImplementedError


class MemoryCacheBackend(CacheBackend):
    def __init__(self) -> None:
        self._entries: dict[str, OrderedDict[str, tuple[bytes, float]]] = defaultdict(
            OrderedDict
        )
        self._max_entries: dict[str, int] = {
            "listings_tile": settings.LISTINGS_TILE_CACHE_MAX_ENTRIES,
            "location_intelligence": settings.LOCATION_INTELLIGENCE_CACHE_MAX_ENTRIES,
            "analytics_tile": 2000,
        }

    @property
    def backend_name(self) -> str:
        return "memory"

    def _touch(self, cache_name: str, key: str) -> None:
        namespace = self._entries[cache_name]
        if key in namespace:
            namespace.move_to_end(key)

    def _purge_expired(self, cache_name: str) -> None:
        namespace = self._entries[cache_name]
        now = time()
        expired_keys = [k for k, (_, expiry) in namespace.items() if expiry < now]
        for key in expired_keys:
            del namespace[key]

    def get_bytes(self, cache_name: str, key: str) -> bytes | None:
        self._purge_expired(cache_name)
        namespace = self._entries[cache_name]
        item = namespace.get(key)
        if item is None:
            return None
        value, expiry = item
        if expiry < time():
            del namespace[key]
            return None
        self._touch(cache_name, key)
        return value

    def set_bytes(
        self, cache_name: str, key: str, value: bytes, ttl_seconds: int
    ) -> None:
        namespace = self._entries[cache_name]
        namespace[key] = (value, time() + ttl_seconds)
        namespace.move_to_end(key)

        max_entries = self._max_entries.get(cache_name, 2000)
        while len(namespace) > max_entries:
            namespace.popitem(last=False)

    def clear_namespace(self, cache_name: str) -> int:
        namespace = self._entries[cache_name]
        count = len(namespace)
        namespace.clear()
        return count

    def namespace_size(self, cache_name: str) -> int:
        self._purge_expired(cache_name)
        return len(self._entries[cache_name])


class RedisCacheBackend(CacheBackend):
    def __init__(self) -> None:
        self._prefix = settings.REDIS_KEY_PREFIX.strip() or "site_select_core"
        self._client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        )

        try:
            self._client.ping()
        except Exception as exc:  # pragma: no cover - startup path only
            raise CacheBackendError(f"Redis unavailable: {exc}") from exc

    @property
    def backend_name(self) -> str:
        return "redis"

    def _key(self, cache_name: str, key: str) -> str:
        return f"{self._prefix}:{cache_name}:{key}"

    def get_bytes(self, cache_name: str, key: str) -> bytes | None:
        return self._client.get(self._key(cache_name, key))

    def set_bytes(
        self, cache_name: str, key: str, value: bytes, ttl_seconds: int
    ) -> None:
        self._client.set(self._key(cache_name, key), value, ex=ttl_seconds)

    def clear_namespace(self, cache_name: str) -> int:
        pattern = f"{self._prefix}:{cache_name}:*"
        deleted = 0
        for key in self._client.scan_iter(match=pattern, count=500):
            deleted += int(self._client.delete(key))
        return deleted

    def namespace_size(self, cache_name: str) -> int:
        pattern = f"{self._prefix}:{cache_name}:*"
        count = 0
        for _ in self._client.scan_iter(match=pattern, count=500):
            count += 1
        return count


def _build_cache_backend() -> CacheBackend:
    if settings.CACHE_BACKEND.lower() == "redis":
        try:
            backend = RedisCacheBackend()
            logger.info("Cache backend initialized: redis")
            return backend
        except CacheBackendError:
            logger.exception("Falling back to memory cache backend")

    logger.info("Cache backend initialized: memory")
    return MemoryCacheBackend()


cache_backend: CacheBackend = _build_cache_backend()


def cache_get_bytes(cache_name: str, key: str) -> bytes | None:
    start = perf_counter()
    backend = cache_backend.backend_name
    result = "miss"
    try:
        value = cache_backend.get_bytes(cache_name, key)
        if value is not None:
            result = "hit"
        return value
    except Exception:  # pragma: no cover - defensive path
        result = "error"
        logger.exception("cache_get_failed backend=%s cache=%s", backend, cache_name)
        return None
    finally:
        cache_backend_metrics.observe(
            backend=backend,
            cache_name=cache_name,
            op="get",
            result=result,
            duration_seconds=perf_counter() - start,
        )


def cache_set_bytes(cache_name: str, key: str, value: bytes, ttl_seconds: int) -> None:
    start = perf_counter()
    backend = cache_backend.backend_name
    result = "ok"
    try:
        cache_backend.set_bytes(cache_name, key, value, ttl_seconds)
    except Exception:  # pragma: no cover - defensive path
        result = "error"
        logger.exception("cache_set_failed backend=%s cache=%s", backend, cache_name)
    finally:
        cache_backend_metrics.observe(
            backend=backend,
            cache_name=cache_name,
            op="set",
            result=result,
            duration_seconds=perf_counter() - start,
        )


def cache_clear_namespace(cache_name: str) -> int:
    start = perf_counter()
    backend = cache_backend.backend_name
    result = "ok"
    deleted = 0
    try:
        deleted = cache_backend.clear_namespace(cache_name)
        return deleted
    except Exception:  # pragma: no cover - defensive path
        result = "error"
        logger.exception("cache_clear_failed backend=%s cache=%s", backend, cache_name)
        return 0
    finally:
        cache_backend_metrics.observe(
            backend=backend,
            cache_name=cache_name,
            op="clear",
            result=result,
            duration_seconds=perf_counter() - start,
        )


def cache_namespace_size(cache_name: str) -> int:
    start = perf_counter()
    backend = cache_backend.backend_name
    result = "ok"
    try:
        return cache_backend.namespace_size(cache_name)
    except Exception:  # pragma: no cover - defensive path
        result = "error"
        logger.exception("cache_size_failed backend=%s cache=%s", backend, cache_name)
        return 0
    finally:
        cache_backend_metrics.observe(
            backend=backend,
            cache_name=cache_name,
            op="size",
            result=result,
            duration_seconds=perf_counter() - start,
        )
