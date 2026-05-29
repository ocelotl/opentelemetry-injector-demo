from __future__ import annotations

from os import getenv
from queue import Empty, Queue
from socket import create_connection, socket
from struct import pack
from threading import Thread
from time import monotonic, sleep
from typing import Any

from msgpack import packb
from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class MessagePackBatchingSidecarExporter(SpanExporter):
    def __init__(self) -> None:
        self.host = getenv("SIDECAR_HOST", "127.0.0.1")
        self.port = int(getenv("SIDECAR_PORT", "9999"))
        self.max_batch_size = int(getenv("SIDECAR_MAX_BATCH_SIZE", "16"))
        self.max_batch_delay_seconds = float(getenv("SIDECAR_MAX_BATCH_DELAY_SECONDS", "0.2"))
        self.reconnect_delay_seconds = float(getenv("SIDECAR_RECONNECT_DELAY_SECONDS", "0.1"))

        self.queue: Queue[dict[str, Any] | None] = Queue()
        self.worker = Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            self.queue.put(
                {
                    "name": span.name,
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": (
                        format(span.parent.span_id, "016x") if span.parent else None
                    ),
                    "kind": str(span.kind),
                    "attributes": dict(span.attributes or {}),
                    "start_time_unix_nano": span.start_time,
                    "end_time_unix_nano": span.end_time,
                }
            )

        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.queue.put(None)
        self.worker.join(timeout=10)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def _connect_once(self) -> socket:
        return create_connection((self.host, self.port), timeout=5)

    def _connect_until_success(self) -> socket:
        while True:
            try:
                sock = self._connect_once()
                print("agent: connected to sidecar", flush=True)
                return sock
            except OSError as exc:
                print(f"agent: sidecar unavailable: {exc}; retrying", flush=True)
                sleep(self.reconnect_delay_seconds)

    def _send_batch(self, sock: socket | None, batch: list[dict[str, Any]]) -> socket:
        payload = packb(batch, use_bin_type=True)
        frame = pack("!I", len(payload)) + payload

        while True:
            if sock is None:
                sock = self._connect_until_success()

            try:
                sock.sendall(frame)
                print(f"agent: sent msgpack batch size={len(batch)}", flush=True)
                return sock
            except OSError as exc:
                print(f"agent: send failed: {exc}; reconnecting", flush=True)
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None
                sleep(self.reconnect_delay_seconds)

    def _worker_loop(self) -> None:
        sock: socket | None = None
        batch: list[dict[str, Any]] = []
        batch_started_at: float | None = None
        should_shutdown = False

        while True:
            timeout = self.max_batch_delay_seconds

            if batch_started_at is not None:
                elapsed = monotonic() - batch_started_at
                timeout = max(0.0, self.max_batch_delay_seconds - elapsed)

            try:
                item = self.queue.get(timeout=timeout)
            except Empty:
                if batch:
                    sock = self._send_batch(sock, batch)
                    batch = []
                    batch_started_at = None

                if should_shutdown:
                    break

                continue

            if item is None:
                should_shutdown = True

                if batch:
                    sock = self._send_batch(sock, batch)
                    batch = []
                    batch_started_at = None

                break

            if not batch:
                batch_started_at = monotonic()

            batch.append(item)

            elapsed = monotonic() - batch_started_at
            should_flush = (
                len(batch) >= self.max_batch_size
                or elapsed >= self.max_batch_delay_seconds
            )

            if should_flush:
                sock = self._send_batch(sock, batch)
                batch = []
                batch_started_at = None

        if sock is not None:
            sock.close()


print("agent: sitecustomize loaded", flush=True)

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(MessagePackBatchingSidecarExporter()))
trace.set_tracer_provider(provider)

RequestsInstrumentor().instrument()

print("agent: tracer provider configured", flush=True)
print("agent: requests instrumentation enabled", flush=True)
print("agent: sidecar protocol=msgpack-batched", flush=True)
