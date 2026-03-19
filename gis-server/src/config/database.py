import logging
from collections import defaultdict
from time import perf_counter

from sqlalchemy import create_engine, event
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import settings

logger = logging.getLogger(__name__)


class DatabasePoolMetrics:
    def __init__(self) -> None:
        self._checkout_timeout_total = 0
        self._query_total = 0
        self._query_errors_total = 0
        self._query_duration_sum_seconds = 0.0
        self._query_duration_bucket_counts: dict[float, int] = defaultdict(int)

    def observe_query(self, duration_seconds: float, is_error: bool) -> None:
        self._query_total += 1
        self._query_duration_sum_seconds += duration_seconds
        if is_error:
            self._query_errors_total += 1

        for bucket in (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0):
            if duration_seconds <= bucket:
                self._query_duration_bucket_counts[bucket] += 1
        if duration_seconds > 2.0:
            self._query_duration_bucket_counts[float("inf")] += 1

    def increment_checkout_timeout(self) -> None:
        self._checkout_timeout_total += 1

    def render_prometheus(self) -> str:
        pool_size = engine.pool.size() if hasattr(engine.pool, "size") else 0
        pool_checked_out = (
            engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else 0
        )
        pool_overflow = (
            engine.pool.overflow() if hasattr(engine.pool, "overflow") else 0
        )

        lines = [
            "# HELP db_pool_size Configured DB pool size",
            "# TYPE db_pool_size gauge",
            f"db_pool_size {pool_size}",
            "# HELP db_pool_checked_out Current checked out DB connections",
            "# TYPE db_pool_checked_out gauge",
            f"db_pool_checked_out {pool_checked_out}",
            "# HELP db_pool_overflow Current DB pool overflow connections",
            "# TYPE db_pool_overflow gauge",
            f"db_pool_overflow {pool_overflow}",
            "# HELP db_pool_checkout_timeout_total Total DB pool checkout timeouts",
            "# TYPE db_pool_checkout_timeout_total counter",
            f"db_pool_checkout_timeout_total {self._checkout_timeout_total}",
            "# HELP db_query_total Total DB queries observed",
            "# TYPE db_query_total counter",
            f"db_query_total {self._query_total}",
            "# HELP db_query_errors_total Total DB query errors observed",
            "# TYPE db_query_errors_total counter",
            f"db_query_errors_total {self._query_errors_total}",
            "# HELP db_query_duration_seconds_sum Total DB query duration seconds",
            "# TYPE db_query_duration_seconds_sum counter",
            f"db_query_duration_seconds_sum {self._query_duration_sum_seconds:.6f}",
            "# HELP db_query_duration_bucket_seconds DB query duration histogram buckets",
            "# TYPE db_query_duration_bucket_seconds counter",
        ]

        for bucket in (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0):
            count = self._query_duration_bucket_counts.get(bucket, 0)
            lines.append(f'db_query_duration_bucket_seconds{{le="{bucket}"}} {count}')
        lines.append(
            f'db_query_duration_bucket_seconds{{le="+Inf"}} {self._query_duration_bucket_counts.get(float("inf"), 0)}'
        )

        return "\n".join(lines) + "\n"


db_pool_metrics = DatabasePoolMetrics()


_connect_args: dict[str, str] = {}
if settings.DATABASE_URL.startswith("postgresql"):
    _connect_args["options"] = (
        f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"
    )

if settings.DB_USE_PGBOUNCER and "+psycopg" in settings.DATABASE_URL:
    # PgBouncer transaction mode works best without prepared statement caching.
    _connect_args["prepared_statement_cache_size"] = "0"

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_use_lifo=True,
    connect_args=_connect_args,
)


@event.listens_for(engine, "before_cursor_execute")
def _on_before_cursor_execute(
    _conn,
    _cursor,
    _statement,
    _parameters,
    context,
    _executemany,
):
    context._query_timer_start = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _on_after_cursor_execute(
    _conn,
    _cursor,
    _statement,
    _parameters,
    context,
    _executemany,
):
    start = getattr(context, "_query_timer_start", None)
    if start is None:
        return
    duration = perf_counter() - start
    db_pool_metrics.observe_query(duration, is_error=False)


@event.listens_for(engine, "handle_error")
def _on_handle_error(_exception_context):
    db_pool_metrics.observe_query(0.0, is_error=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


logger.info("Database module loaded")


def get_db_session():
    """
    FastAPI dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyTimeoutError:
        db_pool_metrics.increment_checkout_timeout()
        raise
    finally:
        db.close()
