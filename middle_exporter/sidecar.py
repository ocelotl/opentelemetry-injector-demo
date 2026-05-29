from __future__ import annotations

from os import getenv
from socket import socket
from socketserver import BaseRequestHandler, TCPServer
from struct import unpack
from typing import Any

from msgpack import unpackb
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags


collector_endpoint = getenv("OTLP_ENDPOINT", "http://collector:4317")

resource = Resource.create(
    {
        "service.name": "msgpack-sidecar",
        "telemetry.sidecar": True,
        "telemetry.sidecar.protocol": "msgpack-batched",
    }
)

exporter = OTLPSpanExporter(endpoint=collector_endpoint, insecure=True)


def read_exactly(sock: socket, byte_count: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = byte_count

    while remaining > 0:
        chunk = sock.recv(remaining)

        if chunk == b"":
            return None

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def read_msgpack_frame(sock: socket) -> list[dict[str, Any]] | None:
    length_bytes = read_exactly(sock, 4)

    if length_bytes is None:
        return None

    payload_length = unpack("!I", length_bytes)[0]
    payload = read_exactly(sock, payload_length)

    if payload is None:
        return None

    value = unpackb(payload, raw=False)

    if isinstance(value, list):
        return value

    return [value]


def span_kind_from_text(value: str) -> SpanKind:
    if value == "SpanKind.CLIENT":
        return SpanKind.CLIENT
    if value == "SpanKind.SERVER":
        return SpanKind.SERVER
    if value == "SpanKind.PRODUCER":
        return SpanKind.PRODUCER
    if value == "SpanKind.CONSUMER":
        return SpanKind.CONSUMER
    return SpanKind.INTERNAL


def readable_span_from_data(span_data: dict[str, Any]) -> ReadableSpan:
    context = SpanContext(
        trace_id=int(span_data["trace_id"], 16),
        span_id=int(span_data["span_id"], 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state={},
    )

    return ReadableSpan(
        name=span_data["name"],
        context=context,
        parent=None,
        resource=resource,
        attributes=span_data.get("attributes", {}),
        events=(),
        links=(),
        kind=span_kind_from_text(span_data.get("kind", "")),
        status=None,
        start_time=span_data["start_time_unix_nano"],
        end_time=span_data["end_time_unix_nano"],
    )


class SpanHandler(BaseRequestHandler):
    def handle(self) -> None:
        while True:
            batch_data = read_msgpack_frame(self.request)

            if batch_data is None:
                return

            spans = [readable_span_from_data(span_data) for span_data in batch_data]
            result = exporter.export(spans)

            print(
                f"sidecar: exported msgpack batch to collector: size={len(spans)} result={result}",
                flush=True,
            )


print("sidecar: listening on 0.0.0.0:9999", flush=True)
print(f"sidecar: exporting OTLP/protobuf to {collector_endpoint}", flush=True)
print("sidecar: sidecar protocol=msgpack-batched", flush=True)

with TCPServer(("0.0.0.0", 9999), SpanHandler) as server:
    server.serve_forever()
