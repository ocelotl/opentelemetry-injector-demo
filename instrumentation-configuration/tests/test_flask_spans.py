"""Verify that Flask HTTP spans are auto-generated via the declarative
instrumentation/development.python.flask config without any OTel imports in
app.py."""

import json
from os.path import join


def _load_spans(traces_jsonl: str) -> list[dict]:
    """Parse all spans from the OTLP JSONL file produced by the file exporter."""
    spans = []
    with open(traces_jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            batch = json.loads(line)
            for resource_spans in batch.get("resourceSpans", []):
                for scope_spans in resource_spans.get("scopeSpans", []):
                    spans.extend(scope_spans.get("spans", []))
    return spans


def _attr(span: dict, key: str):
    """Return the value of a span attribute by key, or None if absent."""
    for kv in span.get("attributes", []):
        if kv["key"] == key:
            v = kv["value"]
            return (
                v.get("stringValue")
                or v.get("intValue")
                or v.get("boolValue")
                or v.get("doubleValue")
            )
    return None


class TestFlaskSpans:
    def test_traces_file_exists(self, output_dir):
        path = join(output_dir, "traces.jsonl")
        assert open(path).read().strip(), "traces.jsonl is empty — no spans were exported"

    def test_flask_spans_present(self, output_dir):
        spans = _load_spans(join(output_dir, "traces.jsonl"))
        assert spans, "No spans found in traces.jsonl"

        # FlaskInstrumentor creates server spans named after the route, e.g.
        # "GET /" and "GET /items/<item_id>".
        names = {s["name"] for s in spans}
        assert any("GET" in name for name in names), (
            f"No GET spans found. Span names: {sorted(names)}\n"
            "This means FlaskInstrumentor was NOT activated — check that the "
            "instrumentation/development.python.flask section in otel-config.yaml "
            "is being processed by configure_sdk()."
        )

    def test_flask_span_has_http_route(self, output_dir):
        spans = _load_spans(join(output_dir, "traces.jsonl"))
        routes = [
            _attr(s, "http.route") or _attr(s, "url.path")
            for s in spans
            if "GET" in s.get("name", "")
        ]
        assert any(routes), (
            "Flask spans found but none have http.route or url.path attribute. "
            f"Span names: {[s['name'] for s in spans]}"
        )

    def test_items_route_traced(self, output_dir):
        spans = _load_spans(join(output_dir, "traces.jsonl"))
        item_spans = [
            s for s in spans
            if "items" in s.get("name", "").lower()
            or _attr(s, "http.route") in ("/items/<int:item_id>", "/items/<item_id>")
        ]
        assert item_spans, (
            "No span for the /items/<item_id> route found. "
            f"All span names: {[s['name'] for s in spans]}"
        )

    def test_no_otel_import_in_app(self):
        """Sanity-check: app.py must not import OpenTelemetry directly."""
        from os.path import dirname
        app_path = join(dirname(dirname(__file__)), "app.py")
        app_source = open(app_path).read()
        assert "opentelemetry" not in app_source, (
            "app.py contains an opentelemetry import — the whole point of this "
            "demo is that the app is unmodified."
        )

