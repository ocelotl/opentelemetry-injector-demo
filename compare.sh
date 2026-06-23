#!/usr/bin/env bash
# Runs the pyprotobuf and protobuf scenarios sequentially, then compares their
# OTLP JSON output to verify both exporters produce semantically identical telemetry.
#
# Requirements: Docker with Compose plugin v2.7+, jq
set -euo pipefail

# Pass host UID/GID to docker compose so prepare-python-agent writes files as the
# host user. Bash's $UID is read-only and not reliably exported, so we use our own
# variable names that docker-compose.yml references via ${SCRIPT_UID}:${SCRIPT_GID}.
export SCRIPT_UID="$(id -u)"
export SCRIPT_GID="$(id -g)"

REPO="$(cd "$(dirname "$0")" && pwd)"
OUT="$REPO/compare-output"

# ── helpers ──────────────────────────────────────────────────────────────────

log() { echo; echo "=== $* ==="; }

# Normalise one signal file for a schema-level comparison that ignores all
# legitimate run-to-run variation. Signal-specific flattening avoids false
# diffs caused by different OTLP batch boundaries between runs.
#
# Traces  — flatten to [span], keep name/kind/status/attribute-keys/events,
#           strip all IDs, timestamps, and timing values (duration_ms).
# Metrics — flatten to [metric], keep name/unit/type/is_monotonic and the SET
#           of attribute keys per metric; strip all data-point values (they
#           depend on export timing and change every run).
# Logs    — flatten to [record], keep severity/body/attributes (minus trace
#           IDs injected by the logging instrumentation), sort stably.
#
# After flattening, sort everything so order-of-arrival doesn't matter.
# Scenario name (pyprotobuf-demo / protobuf-demo) and working-dir path
# (/app/pyprotobuf/ vs /app/protobuf/) are normalised via sed.

normalize_traces() {
    jq -rs '
      [
        .[] | .resourceSpans[] as $rs | $rs.scopeSpans[] as $ss | $ss.spans[] |
        {
          "resource": ($rs.resource.attributes // [] | sort_by(.key)),
          "scope":    $ss.scope.name,
          "name":     .name,
          "kind":     .kind,
          "status":   .status,
          "attributes": (.attributes // [] |
            map(select(.key != "duration_ms")) | sort_by(.key)),
          "events": (.events // [] | map({
            "name": .name,
            "attributes": (.attributes // [] |
              map(select(.key != "duration_ms")) | sort_by(.key))
          }) | sort_by(.name))
        }
      ] | sort_by([.name, (.attributes | tostring)])
    '
}

normalize_metrics() {
    jq -rs '
      [
        .[] | .resourceMetrics[] as $rm | $rm.scopeMetrics[] | .metrics[] |
        # Timing-based histograms: compare schema only (count + bucket boundaries),
        # not sum/min/max/bucketCounts which depend on real network latency.
        # app.request_size uses fixed synthetic values, so its full data is compared.
        . as $metric |
        {
          "resource": ($rm.resource.attributes // [] | sort_by(.key)),
          "name":     .name,
          "unit":     .unit,
          "type": (
            if has("sum")         then "Sum"
            elif has("gauge")     then "Gauge"
            elif has("histogram") then "Histogram"
            else "Unknown" end),
          "is_monotonic": (.sum.isMonotonic // null),
          "temporality":  (.sum.aggregationTemporality //
                           .histogram.aggregationTemporality // null),
          "data_points": (
            if has("sum") or has("gauge") then
              (.sum.dataPoints // .gauge.dataPoints // []) |
              map({ "attributes": (.attributes // [] | sort_by(.key)), "value": (.asInt // .asDouble) }) |
              sort_by((.attributes | tostring))
            elif has("histogram") then
              (.histogram.dataPoints // []) |
              if ($metric.name == "app.request_duration" or $metric.name == "http.client.duration") then
                map({ "attributes": (.attributes // [] | sort_by(.key)), "count": .count, "bounds": (.explicitBounds // []) })
              else
                map({ "attributes": (.attributes // [] | sort_by(.key)), "count": .count, "sum": .sum, "min": .min, "max": .max, "bounds": (.explicitBounds // []), "buckets": (.bucketCounts // []) })
              end |
              sort_by((.attributes | tostring))
            else [] end)
        }
      ] | sort_by(.name)
    '
}

normalize_logs() {
    jq -rs '
      [
        .[] | .resourceLogs[] | .scopeLogs[] | .logRecords[] |
        {
          "severityNumber": .severityNumber,
          "severityText":   .severityText,
          "body":           .body,
          "attributes": (.attributes // [] |
            map(select(
              .key != "otelSpanID" and
              .key != "otelTraceID" and
              .key != "otelTraceSampled"
            )) | sort_by(.key))
        }
      ] | sort_by([
        .severityNumber,
        (.body.stringValue // ""),
        (.attributes | tostring)
      ])
    '
}

normalize() {
    local file=$1
    local signal
    signal="$(basename "$file" .json)"
    "normalize_${signal}" < "$file" \
      | sed 's/pyprotobuf-demo/SCENARIO/g; s/protobuf-demo/SCENARIO/g
             s|/app/pyprotobuf/|/app/SCENARIO/|g
             s|/app/protobuf/|/app/SCENARIO/|g'
}

run_scenario() {
    local name=$1
    local dir=$2
    log "Running $name"
    docker compose -f "$dir/docker-compose.yml" up --detach
    docker compose -f "$dir/docker-compose.yml" wait app
    # Give the collector a moment to flush file exports after the app's final
    # SDK force_flush completes — the OTLP request may arrive at the collector
    # just as docker compose down would otherwise send SIGTERM.
    sleep 3
    docker compose -f "$dir/docker-compose.yml" down --timeout 10
    echo "$name: done"
}

# ── main ─────────────────────────────────────────────────────────────────────

log "Setup"
rm -rf "$OUT"
mkdir -p "$OUT/pyprotobuf" "$OUT/protobuf"
# The otel-collector-contrib image runs as uid 10001; make output dirs world-writable
# so it can create the trace/metric/log JSON files inside them.
chmod 777 "$OUT/pyprotobuf" "$OUT/protobuf"
# Pre-create python-agent dirs as the host user so Docker bind-mounts don't
# recreate them as root (which would deny writes from the non-root container user).
mkdir -p "$REPO/pyprotobuf/python-agent" "$REPO/protobuf/python-agent"

run_scenario "pyprotobuf" "$REPO/pyprotobuf"
run_scenario "protobuf"   "$REPO/protobuf"

log "Comparing outputs"

all_ok=true
for signal in traces metrics logs; do
    f_py="$OUT/pyprotobuf/${signal}.json"
    f_pb="$OUT/protobuf/${signal}.json"

    if [[ ! -f "$f_py" || ! -f "$f_pb" ]]; then
        echo "  MISSING  $signal (one or both output files not found)"
        all_ok=false
        continue
    fi

    if diff <(normalize "$f_py") <(normalize "$f_pb") > /dev/null 2>&1; then
        echo "  OK       $signal"
    else
        echo "  DIFF     $signal:"
        diff <(normalize "$f_py") <(normalize "$f_pb") || true
        all_ok=false
    fi
done

echo
if $all_ok; then
    echo "All signals match — pyprotobuf and protobuf produce equivalent telemetry."
else
    echo "Differences found — see above."
    exit 1
fi
