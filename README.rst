==========================
OpenTelemetry Injector Demo
==========================

This repository proves that ``opentelemetry-exporter-otlp-pyproto`` — a
pure-Python protobuf implementation with **no** ``google.protobuf`` dependency
— produces telemetry that is semantically identical to the standard
``opentelemetry-exporter-otlp-proto`` exporter.

Two self-contained Docker Compose scenarios run the same application with the
same OTel Collector configuration and the same injection mechanism.  The only
difference between them is the exporter package.  A pytest suite runs both,
captures their OTLP output as JSON files, normalises away run-to-run
variation (timestamps, trace IDs, network latency), and diffs the results.

Prerequisites
=============

- Docker with the Compose plugin v2.7+ (``docker compose``)
- `uv <https://docs.astral.sh/uv/>`_

No other local tooling or repository checkouts are required.  All Python
packages used by the application are installed inside Docker containers at
runtime.

Quick start: running the comparison
=====================================

::

    uv run pytest tests/ -v

This will:

1. Delete any previous output in ``compare-output/``.
2. Run the ``pyprotobuf`` scenario end-to-end: installs packages, starts the
   app, waits for it to finish, stops all containers.
3. Run the ``protobuf`` scenario the same way.
4. Normalise both scenarios' OTLP JSON output (see *What is compared* below).
5. Assert signal by signal that the normalised output is identical.

The first run takes several minutes because Docker pulls images and the
``pyprotobuf`` scenario clones ``opentelemetry-python`` from GitHub to install
the pyproto packages.  Subsequent runs reuse Docker layer cache and complete
much faster.

Skipping Docker (use existing output)
--------------------------------------

If you have already run the scenarios and just want to re-run the test logic
without re-running Docker::

    uv run pytest tests/ --no-docker -v

To test against output captured in an arbitrary directory::

    uv run pytest tests/ --output-dir /path/to/output -v

What is compared
================

The OTel Collector writes raw OTLP/JSON to ``compare-output/<scenario>/``
(one file per signal: ``traces.json``, ``metrics.json``, ``logs.json``).
Before comparing, the test suite normalises each file to remove legitimate
run-to-run variation:

**Traces** — flattened to a list of spans; compared on: span name, kind,
status code and message, attribute key/value pairs, event names and their
attributes.  Stripped: trace/span IDs, timestamps, ``duration_ms`` (real
network latency).  Exception stacktraces are compared after replacing the
scenario-specific working-directory path with a placeholder.

**Metrics** — flattened to a list of metric descriptors; compared on:

- ``app.requests`` (Counter): value (always 9 — one per successful request)
- ``app.active_requests`` (UpDownCounter): value (always 0 — balanced +1/−1)
- ``app.memory_usage`` (Gauge): value (always 42.5 — fixed synthetic callback)
- ``app.request_size`` (Histogram): full data — count, sum, min, max, bucket
  counts (fixed synthetic values: 512 By per success, 64 By per error)
- ``app.request_duration`` (Histogram): observation count only (real latency
  values stripped)
- ``http.client.duration`` (Histogram): observation count only (real latency
  values stripped)

**Logs** — flattened to a list of records across all OTLP batches; compared
on: severity number/text, body, attribute key/value pairs.  Stripped: trace
correlation attributes (``otelSpanID``, ``otelTraceID``, ``otelTraceSampled``).

On failure each test prints a full unified diff of the normalised outputs so
the exact discrepancy is visible without any additional tooling.

Scenarios
=========

``pyprotobuf/``
   Uses ``opentelemetry-exporter-otlp-pyproto-http``, installed from the
   ``pyproto`` branch of https://github.com/ocelotl/opentelemetry-python.
   No ``google.protobuf`` anywhere in the dependency tree.

``protobuf/``
   Uses ``opentelemetry-exporter-otlp-proto-http``, installed from PyPI.
   Pulls in ``protobuf`` and ``googleapis-common-protos`` as usual.

Both scenarios exercise the same telemetry features:

- **Traces** — parent/child spans (Internal + Client kinds), span events
  (``request.started``, ``request.done``), span status OK and ERROR,
  ``span.record_exception`` with full stacktrace, attributes of all value
  types (string, int, bool, float, array).
- **Metrics** — monotonic counter (``Sum``), up-down counter (``Sum``,
  non-monotonic), manual histogram, observable gauge, synthetic fixed-value
  histogram, plus the auto-instrumented ``http.client.duration`` histogram.
- **Logs** — log records with ``SeverityText``, ``Body``, and trace
  correlation (``trace_id`` / ``span_id`` embedded).

Injection mechanism
===================

Both scenarios use the `OpenTelemetry Injector
<https://github.com/open-telemetry/opentelemetry-injector>`_ (``LD_PRELOAD``):

1. A ``prepare-python-agent`` Docker service installs all packages into
   ``./python-agent/glibc/`` (the libc-flavour subdirectory the injector
   expects).
2. The app container installs the ``opentelemetry-injector`` ``.deb`` package
   and writes ``/etc/opentelemetry/injector/injector.conf`` with the agent
   path prefix, then launches Python with
   ``LD_PRELOAD=/usr/lib/opentelemetry/libotelinject.so``.
3. At process start the injector reads ``injector.conf``, detects the libc
   flavour, appends ``glibc/`` to the configured path prefix, and prepends
   the result to ``PYTHONPATH``.
4. Python automatically executes ``sitecustomize.py`` before any user code,
   which wires up the SDK and exporters.

The application source code (``app.py``) uses the OpenTelemetry API (tracing,
metrics) but contains no SDK or exporter configuration — all wiring is handled
by the injected ``sitecustomize.py``.

Running a single scenario manually
====================================

Each scenario is self-contained.  From the repository root::

    cd pyprotobuf && docker compose up

or::

    cd protobuf && docker compose up

The OTel Collector's debug exporter prints all received spans, metrics, and
log records to stdout.  Request index 9 targets an unreachable address
intentionally, producing an ERROR span with an ``exception`` event and full
stacktrace.  The two scenarios use separate Docker networks and can run
simultaneously without port conflicts.

Dependencies installed
======================

``pyprotobuf`` scenario (no ``google.protobuf``)::

    opentelemetry-api
    opentelemetry-sdk
    opentelemetry-pyproto              (pure-Python protobuf messages)
    opentelemetry-exporter-otlp-pyproto-common
    opentelemetry-exporter-otlp-pyproto-http
    opentelemetry-instrumentation-requests
    opentelemetry-instrumentation-logging
    requests

``protobuf`` scenario::

    opentelemetry-api
    opentelemetry-sdk
    opentelemetry-exporter-otlp-proto-http  (+ protobuf, googleapis-common-protos)
    opentelemetry-instrumentation-requests
    opentelemetry-instrumentation-logging
    requests
