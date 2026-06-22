from __future__ import annotations

from opentelemetry import metrics
from requests import get

meter = metrics.get_meter("pyproto-demo")
request_counter = meter.create_counter(
    "app.requests",
    unit="{request}",
    description="Number of outbound HTTP requests made by the app",
)

print("app: started", flush=True)

for index in range(10):
    response = get("https://example.com", timeout=10)
    request_counter.add(1, {"http.status_code": str(response.status_code)})
    print(f"app: request {index} -> {response.status_code}", flush=True)

print("app: done", flush=True)
