"""Lightweight in-process observability utilities."""

from __future__ import annotations

from collections import defaultdict


REQUEST_DURATION_BUCKETS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
LOCATION_INTELLIGENCE_DURATION_BUCKETS_SECONDS = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)


class RequestMetrics:
    def __init__(self) -> None:
        self._request_total = 0
        self._request_errors_total = 0
        self._duration_sum_seconds = 0.0
        self._duration_count = 0
        self._duration_bucket_counts: dict[float, int] = defaultdict(int)
        self._status_counts: dict[str, int] = defaultdict(int)
        self._route_counts: dict[str, int] = defaultdict(int)

    def observe_request(
        self, method: str, path: str, status_code: int, duration_seconds: float
    ) -> None:
        self._request_total += 1
        self._duration_sum_seconds += duration_seconds
        self._duration_count += 1
        if status_code >= 500:
            self._request_errors_total += 1

        status_key = str(status_code)
        route_key = f"{method} {path}"
        self._status_counts[status_key] += 1
        self._route_counts[route_key] += 1

        for bucket in REQUEST_DURATION_BUCKETS_SECONDS:
            if duration_seconds <= bucket:
                self._duration_bucket_counts[bucket] += 1
        if duration_seconds > REQUEST_DURATION_BUCKETS_SECONDS[-1]:
            self._duration_bucket_counts[float("inf")] += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP api_requests_total Total API requests",
            "# TYPE api_requests_total counter",
            f"api_requests_total {self._request_total}",
            "# HELP api_request_errors_total Total API 5xx responses",
            "# TYPE api_request_errors_total counter",
            f"api_request_errors_total {self._request_errors_total}",
            "# HELP api_request_duration_seconds Request duration summary",
            "# TYPE api_request_duration_seconds summary",
            f"api_request_duration_seconds_sum {self._duration_sum_seconds:.6f}",
            f"api_request_duration_seconds_count {self._duration_count}",
            "# HELP api_request_duration_bucket_seconds Request duration histogram buckets",
            "# TYPE api_request_duration_bucket_seconds counter",
        ]

        for bucket in REQUEST_DURATION_BUCKETS_SECONDS:
            bucket_count = self._duration_bucket_counts.get(bucket, 0)
            lines.append(
                f'api_request_duration_bucket_seconds{{le="{bucket}"}} {bucket_count}'
            )
        lines.append(
            f'api_request_duration_bucket_seconds{{le="+Inf"}} {self._duration_bucket_counts.get(float("inf"), 0)}'
        )

        lines.extend(
            [
                "# HELP api_requests_by_status_total Request count grouped by status code",
                "# TYPE api_requests_by_status_total counter",
            ]
        )
        for status_code, count in sorted(self._status_counts.items()):
            lines.append(
                f'api_requests_by_status_total{{status="{status_code}"}} {count}'
            )

        lines.extend(
            [
                "# HELP api_requests_by_route_total Request count grouped by method and path",
                "# TYPE api_requests_by_route_total counter",
            ]
        )
        for route, count in sorted(self._route_counts.items()):
            method, path = route.split(" ", 1)
            lines.append(
                f'api_requests_by_route_total{{method="{method}",path="{path}"}} {count}'
            )

        return "\n".join(lines) + "\n"


request_metrics = RequestMetrics()


class LocationIntelligenceMetrics:
    def __init__(self) -> None:
        self._stage_total: dict[str, int] = defaultdict(int)
        self._stage_error_total: dict[str, int] = defaultdict(int)
        self._stage_duration_sum_seconds: dict[str, float] = defaultdict(float)
        self._stage_duration_bucket_counts: dict[str, dict[float, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def observe_stage(
        self, stage: str, duration_seconds: float, is_error: bool = False
    ) -> None:
        self._stage_total[stage] += 1
        self._stage_duration_sum_seconds[stage] += duration_seconds
        if is_error:
            self._stage_error_total[stage] += 1

        for bucket in LOCATION_INTELLIGENCE_DURATION_BUCKETS_SECONDS:
            if duration_seconds <= bucket:
                self._stage_duration_bucket_counts[stage][bucket] += 1
        if duration_seconds > LOCATION_INTELLIGENCE_DURATION_BUCKETS_SECONDS[-1]:
            self._stage_duration_bucket_counts[stage][float("inf")] += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP location_intelligence_stage_total Total executions by location intelligence stage",
            "# TYPE location_intelligence_stage_total counter",
        ]
        for stage, count in sorted(self._stage_total.items()):
            lines.append(
                f'location_intelligence_stage_total{{stage="{stage}"}} {count}'
            )

        lines.extend(
            [
                "# HELP location_intelligence_stage_errors_total Total failures by location intelligence stage",
                "# TYPE location_intelligence_stage_errors_total counter",
            ]
        )
        for stage, count in sorted(self._stage_error_total.items()):
            lines.append(
                f'location_intelligence_stage_errors_total{{stage="{stage}"}} {count}'
            )

        lines.extend(
            [
                "# HELP location_intelligence_stage_duration_seconds_sum Total stage duration seconds",
                "# TYPE location_intelligence_stage_duration_seconds_sum counter",
            ]
        )
        for stage, value in sorted(self._stage_duration_sum_seconds.items()):
            lines.append(
                f'location_intelligence_stage_duration_seconds_sum{{stage="{stage}"}} {value:.6f}'
            )

        lines.extend(
            [
                "# HELP location_intelligence_stage_duration_bucket_seconds Stage duration histogram buckets",
                "# TYPE location_intelligence_stage_duration_bucket_seconds counter",
            ]
        )

        for stage, buckets in sorted(self._stage_duration_bucket_counts.items()):
            for bucket in LOCATION_INTELLIGENCE_DURATION_BUCKETS_SECONDS:
                count = buckets.get(bucket, 0)
                lines.append(
                    f'location_intelligence_stage_duration_bucket_seconds{{stage="{stage}",le="{bucket}"}} {count}'
                )
            lines.append(
                f'location_intelligence_stage_duration_bucket_seconds{{stage="{stage}",le="+Inf"}} {buckets.get(float("inf"), 0)}'
            )

        return "\n".join(lines) + "\n"


location_intelligence_metrics = LocationIntelligenceMetrics()


class CacheBackendMetrics:
    def __init__(self) -> None:
        self._operations_total: dict[tuple[str, str, str, str], int] = defaultdict(int)
        self._duration_sum_seconds: dict[tuple[str, str, str], float] = defaultdict(
            float
        )
        self._duration_bucket_counts: dict[tuple[str, str, str], dict[float, int]] = (
            defaultdict(lambda: defaultdict(int))
        )

    def observe(
        self,
        backend: str,
        cache_name: str,
        op: str,
        result: str,
        duration_seconds: float,
    ) -> None:
        self._operations_total[(backend, cache_name, op, result)] += 1
        duration_key = (backend, cache_name, op)
        self._duration_sum_seconds[duration_key] += duration_seconds

        for bucket in (0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1):
            if duration_seconds <= bucket:
                self._duration_bucket_counts[duration_key][bucket] += 1
        if duration_seconds > 0.1:
            self._duration_bucket_counts[duration_key][float("inf")] += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP cache_backend_operations_total Total cache backend operations",
            "# TYPE cache_backend_operations_total counter",
        ]

        for (backend, cache_name, op, result), count in sorted(
            self._operations_total.items()
        ):
            lines.append(
                "cache_backend_operations_total"
                f'{{backend="{backend}",cache_name="{cache_name}",op="{op}",result="{result}"}} {count}'
            )

        lines.extend(
            [
                "# HELP cache_backend_operation_duration_seconds_sum Total cache operation duration",
                "# TYPE cache_backend_operation_duration_seconds_sum counter",
            ]
        )
        for (backend, cache_name, op), value in sorted(
            self._duration_sum_seconds.items()
        ):
            lines.append(
                "cache_backend_operation_duration_seconds_sum"
                f'{{backend="{backend}",cache_name="{cache_name}",op="{op}"}} {value:.6f}'
            )

        lines.extend(
            [
                "# HELP cache_backend_operation_duration_bucket_seconds Cache operation latency buckets",
                "# TYPE cache_backend_operation_duration_bucket_seconds counter",
            ]
        )
        for (backend, cache_name, op), buckets in sorted(
            self._duration_bucket_counts.items()
        ):
            for bucket in (0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1):
                lines.append(
                    "cache_backend_operation_duration_bucket_seconds"
                    f'{{backend="{backend}",cache_name="{cache_name}",op="{op}",le="{bucket}"}} {buckets.get(bucket, 0)}'
                )
            lines.append(
                "cache_backend_operation_duration_bucket_seconds"
                f'{{backend="{backend}",cache_name="{cache_name}",op="{op}",le="+Inf"}} {buckets.get(float("inf"), 0)}'
            )

        return "\n".join(lines) + "\n"


cache_backend_metrics = CacheBackendMetrics()
