"""
Port of the jq normalization logic in compare.sh.

Each normalize_* function accepts a path to an NDJSON file (one OTLP export
batch per line), strips all run-to-run volatile fields, and returns a sorted
list of dicts ready for equality comparison.

Scenario names and working-dir paths are unified via _apply_scenario_subs so
that pyprotobuf-demo and protobuf-demo produce identical normalized output.
"""

from json import dumps, loads

# Pairs: (old, new).  Order matters — longer prefix first.
_SCENARIO_SUBS = [
    ("pyprotobuf-demo", "SCENARIO"),
    ("protobuf-demo", "SCENARIO"),
    ("/app/pyprotobuf/", "/app/SCENARIO/"),
    ("/app/protobuf/", "/app/SCENARIO/"),
]

# Histograms whose timing-dependent fields (sum/min/max/bucketCounts) are NOT
# compared — only schema (count + bucket boundaries) is stable across runs.
_TIMING_HISTOGRAMS = {"app.request_duration", "http.client.duration"}


def _apply_scenario_subs(text: str) -> str:
    for old, new in _SCENARIO_SUBS:
        text = text.replace(old, new)
    return text


def _load_ndjson(path: str) -> list:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(loads(line))
    return records


def _sort_attrs(attrs: list) -> list:
    return sorted(attrs or [], key=lambda a: a.get("key", ""))


def _filter_attrs(attrs: list, exclude: set) -> list:
    return [a for a in (attrs or []) if a.get("key") not in exclude]


def _serialized_attrs(attrs: list) -> str:
    return dumps(attrs, sort_keys=True)


# ── traces ────────────────────────────────────────────────────────────────────


def normalize_traces(path: str) -> list:
    """
    Flatten to spans. Keep name/kind/status/attributes/events.
    Strip all IDs, timestamps, and duration_ms values.
    Sort by [name, attributes].
    """
    spans = []
    for record in _load_ndjson(path):
        for rs in record.get("resourceSpans", []):
            resource = _sort_attrs(
                _filter_attrs(
                    rs.get("resource", {}).get("attributes", []),
                    {"service.instance.id"},
                )
            )
            for ss in rs.get("scopeSpans", []):
                scope = ss.get("scope", {}).get("name", "")
                for span in ss.get("spans", []):
                    attrs = _sort_attrs(
                        _filter_attrs(span.get("attributes", []), {"duration_ms"})
                    )
                    events = sorted(
                        [
                            {
                                "name": e.get("name", ""),
                                "attributes": _sort_attrs(
                                    _filter_attrs(
                                        e.get("attributes", []), {"duration_ms"}
                                    )
                                ),
                            }
                            for e in span.get("events", [])
                        ],
                        key=lambda e: e["name"],
                    )
                    spans.append(
                        {
                            "resource": resource,
                            "scope": scope,
                            "name": span.get("name", ""),
                            "kind": span.get("kind"),
                            "status": span.get("status", {}),
                            "attributes": attrs,
                            "events": events,
                        }
                    )

    spans.sort(key=lambda s: [s["name"], _serialized_attrs(s["attributes"])])
    return loads(_apply_scenario_subs(dumps(spans)))


# ── metrics ───────────────────────────────────────────────────────────────────


def normalize_metrics(path: str) -> list:
    """
    Flatten to metrics. Keep name/unit/type/is_monotonic/temporality and
    normalized data_points (attribute keys + stable values only).
    For timing histograms strip sum/min/max/bucketCounts.
    Sort by name.
    """
    metrics = []
    for record in _load_ndjson(path):
        for rm in record.get("resourceMetrics", []):
            resource = _sort_attrs(
                _filter_attrs(
                    rm.get("resource", {}).get("attributes", []),
                    {"service.instance.id"},
                )
            )
            for sm in rm.get("scopeMetrics", []):
                for metric in sm.get("metrics", []):
                    name = metric.get("name", "")

                    if "sum" in metric:
                        mtype = "Sum"
                        is_monotonic = metric["sum"].get("isMonotonic", None)
                        temporality = metric["sum"].get("aggregationTemporality", None)
                        data_points = sorted(
                            [
                                {
                                    "attributes": _sort_attrs(dp.get("attributes", [])),
                                    "value": dp.get("asInt", dp.get("asDouble")),
                                }
                                for dp in metric["sum"].get("dataPoints", [])
                            ],
                            key=lambda dp: _serialized_attrs(dp["attributes"]),
                        )

                    elif "gauge" in metric:
                        mtype = "Gauge"
                        is_monotonic = None
                        temporality = None
                        data_points = sorted(
                            [
                                {
                                    "attributes": _sort_attrs(dp.get("attributes", [])),
                                    "value": dp.get("asInt", dp.get("asDouble")),
                                }
                                for dp in metric["gauge"].get("dataPoints", [])
                            ],
                            key=lambda dp: _serialized_attrs(dp["attributes"]),
                        )

                    elif "histogram" in metric:
                        mtype = "Histogram"
                        is_monotonic = None
                        temporality = metric["histogram"].get(
                            "aggregationTemporality", None
                        )
                        timing_only = name in _TIMING_HISTOGRAMS
                        raw_dps = []
                        for dp in metric["histogram"].get("dataPoints", []):
                            entry = {
                                "attributes": _sort_attrs(dp.get("attributes", [])),
                                "count": dp.get("count"),
                                "bounds": dp.get("explicitBounds", []),
                            }
                            if not timing_only:
                                entry["sum"] = dp.get("sum")
                                entry["min"] = dp.get("min")
                                entry["max"] = dp.get("max")
                                entry["buckets"] = dp.get("bucketCounts", [])
                            raw_dps.append(entry)
                        data_points = sorted(
                            raw_dps,
                            key=lambda dp: _serialized_attrs(dp["attributes"]),
                        )

                    else:
                        mtype = "Unknown"
                        is_monotonic = None
                        temporality = None
                        data_points = []

                    metrics.append(
                        {
                            "resource": resource,
                            "name": name,
                            "unit": metric.get("unit", ""),
                            "type": mtype,
                            "is_monotonic": is_monotonic,
                            "temporality": temporality,
                            "data_points": data_points,
                        }
                    )

    metrics.sort(key=lambda m: m["name"])
    return loads(_apply_scenario_subs(dumps(metrics)))


# ── logs ──────────────────────────────────────────────────────────────────────


def normalize_logs(path: str) -> list:
    """
    Flatten to log records. Keep severity/body/attributes.
    Strip trace-context keys injected by the logging instrumentation.
    Sort by [severityNumber, body text, attributes].
    """
    _TRACE_KEYS = {"otelSpanID", "otelTraceID", "otelTraceSampled"}
    records = []
    for record in _load_ndjson(path):
        for rl in record.get("resourceLogs", []):
            for sl in rl.get("scopeLogs", []):
                for lr in sl.get("logRecords", []):
                    attrs = _sort_attrs(
                        _filter_attrs(lr.get("attributes", []), _TRACE_KEYS)
                    )
                    records.append(
                        {
                            "severityNumber": lr.get("severityNumber"),
                            "severityText": lr.get("severityText", ""),
                            "body": lr.get("body", {}),
                            "attributes": attrs,
                        }
                    )

    records.sort(
        key=lambda r: [
            r.get("severityNumber") or 0,
            r.get("body", {}).get("stringValue", ""),
            _serialized_attrs(r.get("attributes", [])),
        ]
    )
    return loads(_apply_scenario_subs(dumps(records)))
