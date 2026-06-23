#!/usr/bin/env bash
# Runs the pyprotobuf and protobuf scenarios sequentially, then compares their
# OTLP JSON output to verify both exporters produce semantically identical telemetry.
#
# Requirements: Docker with Compose plugin v2.7+, jq
set -euo pipefail

# Export UID/GID so docker-compose can run prepare-python-agent as the host user.
# (Bash defines UID as a read-only variable; it must be explicitly exported.)
export UID="$(id -u)"
export GID="$(id -g)"

REPO="$(cd "$(dirname "$0")" && pwd)"
OUT="$REPO/compare-output"

# ── helpers ──────────────────────────────────────────────────────────────────

log() { echo; echo "=== $* ==="; }

# Normalise one signal file for comparison:
#   • remove time-varying IDs (traceId, spanId, parentSpanId)
#   • remove all timestamps (*UnixNano)
#   • remove histogram timing values (sum, min, max, bucketCounts, explicitBounds)
#     because actual HTTP latencies differ between runs
#   • replace service.name strings so both scenarios compare as "SCENARIO"
#   • sort top-level export-request objects for deterministic ordering
normalize() {
    local file=$1
    jq -rs '
      [ .[] |
        walk(
          if type == "object" then
            del(.traceId, .spanId, .parentSpanId,
                .startTimeUnixNano, .endTimeUnixNano,
                .timeUnixNano, .observedTimeUnixNano) |
            if has("bucketCounts") then
              del(.sum, .min, .max, .bucketCounts, .explicitBounds)
            else . end
          else . end
        )
      ] | sort_by(tostring)
    ' "$file" \
    | sed 's/pyprotobuf-demo/SCENARIO/g; s/protobuf-demo/SCENARIO/g'
}

run_scenario() {
    local name=$1
    local dir=$2
    log "Running $name"
    docker compose -f "$dir/docker-compose.yml" up --detach
    docker compose -f "$dir/docker-compose.yml" wait app
    docker compose -f "$dir/docker-compose.yml" down --timeout 5
    echo "$name: done"
}

# ── main ─────────────────────────────────────────────────────────────────────

log "Setup"
rm -rf "$OUT"
mkdir -p "$OUT/pyprotobuf" "$OUT/protobuf"

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
