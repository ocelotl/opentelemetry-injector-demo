from __future__ import annotations

from requests import get


print("app: started", flush=True)

for index in range(100):
    response = get("https://example.com", timeout=10)
    print(f"app: request {index} -> {response.status_code}", flush=True)

print("app: done", flush=True)
