"""
Benchmark: pyproto (pure-Python) vs google.protobuf (C extension) encoding speed.

Directly benchmarks SerializeToString() on equivalent OTLP message structures.
No OpenTelemetry SDK, tracer, or exporter is involved — raw message encoding only.

Run:
    uv run pytest tests/test_benchmark.py -v --benchmark-sort=mean
"""

from os.path import dirname, abspath, exists, join
from sys import path as _sys_path

# Add both python-agent dirs so we can import pyproto and google.protobuf OTLP
# classes side by side.  These directories are populated by running the Docker
# scenarios with `uv run pytest tests/`.
_REPO = dirname(dirname(abspath(__file__)))
for _d in (
    join(_REPO, "pyprotobuf", "python-agent", "glibc"),
    join(_REPO, "protobuf", "python-agent", "glibc"),
):
    if exists(_d) and _d not in _sys_path:
        _sys_path.insert(0, _d)

from pytest import importorskip

_pt = importorskip(
    "opentelemetry.pyproto.trace.v1.trace_pypb2",
    reason="pyproto not installed — run `uv run pytest tests/` first",
)
_pc = importorskip(
    "opentelemetry.pyproto.common.v1.common_pypb2",
    reason="pyproto not installed — run `uv run pytest tests/` first",
)
_pr = importorskip(
    "opentelemetry.pyproto.resource.v1.resource_pypb2",
    reason="pyproto not installed — run `uv run pytest tests/` first",
)
_bt = importorskip(
    "opentelemetry.proto.trace.v1.trace_pb2",
    reason="google.protobuf OTLP protos not installed — run `uv run pytest tests/` first",
)
_bc = importorskip(
    "opentelemetry.proto.common.v1.common_pb2",
    reason="google.protobuf OTLP protos not installed — run `uv run pytest tests/` first",
)
_br = importorskip(
    "opentelemetry.proto.resource.v1.resource_pb2",
    reason="google.protobuf OTLP protos not installed — run `uv run pytest tests/` first",
)


_TRACE_ID  = bytes.fromhex("d5b0ad8cc68c11c8c5ea29312268b11f")
_SPAN_ID   = bytes.fromhex("bf9196f91510fe64")
_PARENT_ID = bytes.fromhex("50bd84bbf20ab05b")
_T_START   = 1782401900556236527
_T_END     = 1782401900795659167

_N_BATCH_SPANS = 10


def _make_pyproto_span():
    KV, AV, Arr = _pc.KeyValue, _pc.AnyValue, _pc.ArrayValue
    return _pt.Span(
        trace_id=_TRACE_ID,
        span_id=_SPAN_ID,
        parent_span_id=_PARENT_ID,
        flags=256,
        name="process_request",
        kind=1,
        start_time_unix_nano=_T_START,
        end_time_unix_nano=_T_END,
        attributes=[
            KV(key="app.index",   value=AV(int_value=3)),
            KV(key="app.dry_run", value=AV(bool_value=True)),
            KV(key="app.weight",  value=AV(double_value=1.5)),
            KV(key="app.tags",    value=AV(array_value=Arr(values=[
                AV(string_value="demo"), AV(string_value="http"),
            ]))),
        ],
        events=[
            _pt.Span.Event(
                time_unix_nano=_T_START + 1_000,
                name="request.started",
                attributes=[
                    KV(key="index", value=AV(int_value=3)),
                    KV(key="url",   value=AV(string_value="https://example.com/api/v1/data")),
                ],
            ),
            _pt.Span.Event(
                time_unix_nano=_T_END - 1_000,
                name="request.done",
                attributes=[
                    KV(key="status_code", value=AV(int_value=200)),
                    KV(key="duration_ms", value=AV(double_value=234.46)),
                ],
            ),
        ],
        status=_pt.Status(code=1),
    )


def _make_pb_span():
    KV, AV, Arr = _bc.KeyValue, _bc.AnyValue, _bc.ArrayValue
    return _bt.Span(
        trace_id=_TRACE_ID,
        span_id=_SPAN_ID,
        parent_span_id=_PARENT_ID,
        flags=256,
        name="process_request",
        kind=1,
        start_time_unix_nano=_T_START,
        end_time_unix_nano=_T_END,
        attributes=[
            KV(key="app.index",   value=AV(int_value=3)),
            KV(key="app.dry_run", value=AV(bool_value=True)),
            KV(key="app.weight",  value=AV(double_value=1.5)),
            KV(key="app.tags",    value=AV(array_value=Arr(values=[
                AV(string_value="demo"), AV(string_value="http"),
            ]))),
        ],
        events=[
            _bt.Span.Event(
                time_unix_nano=_T_START + 1_000,
                name="request.started",
                attributes=[
                    KV(key="index", value=AV(int_value=3)),
                    KV(key="url",   value=AV(string_value="https://example.com/api/v1/data")),
                ],
            ),
            _bt.Span.Event(
                time_unix_nano=_T_END - 1_000,
                name="request.done",
                attributes=[
                    KV(key="status_code", value=AV(int_value=200)),
                    KV(key="duration_ms", value=AV(double_value=234.46)),
                ],
            ),
        ],
        status=_bt.Status(code=1),
    )


def _make_pyproto_resource_spans():
    KV, AV = _pc.KeyValue, _pc.AnyValue
    scope = _pc.InstrumentationScope(name="opentelemetry.injector.demo", version="1.0.0")
    resource = _pr.Resource(attributes=[
        KV(key="service.name",    value=AV(string_value="demo-service")),
        KV(key="service.version", value=AV(string_value="1.0.0")),
        KV(key="host.name",       value=AV(string_value="worker-01")),
    ])
    spans = [_make_pyproto_span() for _ in range(_N_BATCH_SPANS)]
    return _pt.ResourceSpans(
        resource=resource,
        scope_spans=[_pt.ScopeSpans(scope=scope, spans=spans)],
    )


def _make_pb_resource_spans():
    KV, AV = _bc.KeyValue, _bc.AnyValue
    scope = _bc.InstrumentationScope(name="opentelemetry.injector.demo", version="1.0.0")
    resource = _br.Resource(attributes=[
        KV(key="service.name",    value=AV(string_value="demo-service")),
        KV(key="service.version", value=AV(string_value="1.0.0")),
        KV(key="host.name",       value=AV(string_value="worker-01")),
    ])
    spans = [_make_pb_span() for _ in range(_N_BATCH_SPANS)]
    return _bt.ResourceSpans(
        resource=resource,
        scope_spans=[_bt.ScopeSpans(scope=scope, spans=spans)],
    )


_PYPROTO_SPAN          = _make_pyproto_span()
_PB_SPAN               = _make_pb_span()
_PYPROTO_RESOURCE_SPANS = _make_pyproto_resource_spans()
_PB_RESOURCE_SPANS      = _make_pb_resource_spans()


def test_encode_outputs_identical_span():
    assert _make_pyproto_span().SerializeToString() == _make_pb_span().SerializeToString()


def test_encode_outputs_identical_resource_spans():
    assert (
        _make_pyproto_resource_spans().SerializeToString()
        == _make_pb_resource_spans().SerializeToString()
    )


def test_encode_span_pyproto(benchmark):
    result = benchmark(_PYPROTO_SPAN.SerializeToString)
    assert len(result) > 0


def test_encode_span_protobuf(benchmark):
    result = benchmark(_PB_SPAN.SerializeToString)
    assert len(result) > 0


def test_encode_resource_spans_pyproto(benchmark):
    result = benchmark(_PYPROTO_RESOURCE_SPANS.SerializeToString)
    assert len(result) > 0


def test_encode_resource_spans_protobuf(benchmark):
    result = benchmark(_PB_RESOURCE_SPANS.SerializeToString)
    assert len(result) > 0
