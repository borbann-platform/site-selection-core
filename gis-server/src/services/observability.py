"""Lightweight in-process observability utilities."""

from __future__ import annotations

from collections import defaultdict


REQUEST_DURATION_BUCKETS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


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
