from __future__ import annotations

from logging import getLogger
from time import monotonic

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode
from requests import get

logger = getLogger(__name__)
tracer = trace.get_tracer("demo")
meter = metrics.get_meter("demo")

# Sum (monotonic counter)
request_counter = meter.create_counter(
    "app.requests",
    unit="{request}",
    description="Number of outbound HTTP requests made by the app",
)

# UpDownCounter
active_requests = meter.create_up_down_counter(
    "app.active_requests",
    unit="{request}",
    description="Number of in-flight requests",
)

# Manual histogram (separate from the auto-instrumented http.client.duration)
request_duration = meter.create_histogram(
    "app.request_duration",
    unit="ms",
    description="Duration of outbound HTTP requests",
)

# Synthetic histogram with fixed per-outcome values so compare.sh can verify
# full histogram encoding (count, sum, min, max, bucketCounts) deterministically
# across runs without depending on real network timing.
request_size = meter.create_histogram(
    "app.request_size",
    unit="By",
    description="Simulated request payload size (fixed synthetic values for deterministic comparison)",
)

# ObservableGauge — exercises async instrument + float value encoding
def observe_memory(_options):
    yield metrics.Observation(42.5, {"unit": "MB"})

meter.create_observable_gauge(
    "app.memory_usage",
    callbacks=[observe_memory],
    unit="MB",
    description="Simulated memory usage",
)

print("app: started", flush=True)

for index in range(10):
    # Last request deliberately targets a non-existent host to exercise the ERROR path
    url = "https://example.com" if index < 9 else "http://localhost:19999"

    with tracer.start_as_current_span(
        "process_request",
        attributes={
            "app.index": index,           # int
            "app.dry_run": False,         # bool
            "app.weight": 1.5,            # double
            "app.tags": ["demo", "http"], # array of strings
        },
    ) as span:
        active_requests.add(1, {"phase": "in-flight"})
        span.add_event("request.started", {"index": index, "url": url})

        try:
            t0 = monotonic()
            response = get(url, timeout=2)
            duration_ms = (monotonic() - t0) * 1000

            request_counter.add(1, {"http.status_code": str(response.status_code)})
            request_duration.record(duration_ms, {"http.status_code": str(response.status_code)})
            request_size.record(512, {"result": "success"})
            active_requests.add(-1, {"phase": "in-flight"})

            span.add_event("request.done", {
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            })
            span.set_status(Status(StatusCode.OK))

            logger.info(
                "request completed",
                extra={"index": index, "status_code": response.status_code},
            )
            print(f"app: request {index} -> {response.status_code}", flush=True)

        except Exception as exc:
            request_size.record(64, {"result": "error"})
            active_requests.add(-1, {"phase": "in-flight"})
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.error("request failed", extra={"index": index, "error": str(exc)})
            print(f"app: request {index} -> ERROR: {exc}", flush=True)

print("app: done", flush=True)
