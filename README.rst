==========================
OpenTelemetry Injector Demo
==========================

This repository demonstrates that the ``opentelemetry-exporter-otlp-pyproto``
exporter stack — a pure-Python protobuf implementation with **no**
``google.protobuf`` dependency — produces telemetry that is semantically
identical to the standard ``opentelemetry-exporter-otlp-proto`` exporter.

Two self-contained scenarios run the same application, the same collector
configuration, and the same injection mechanism. The only difference is the
exporter package.

Scenarios
=========

``pyprotobuf/``
   Uses ``opentelemetry-exporter-otlp-pyproto-http``, installed from the local
   ``opentelemetry-python`` checkout.  No ``google.protobuf`` in the dependency
   tree.

``protobuf/``
   Uses ``opentelemetry-exporter-otlp-proto-http``, installed from PyPI.
   Pulls in ``protobuf`` and ``googleapis-common-protos`` as usual.

Both scenarios exercise the same telemetry features:

- **Traces** — parent/child spans (Internal + Client kinds), span events
  (``request.started``, ``request.done``), span status OK and ERROR,
  ``span.record_exception`` with full stacktrace, attributes of all value
  types (string, int, bool, float, array).
- **Metrics** — monotonic counter (``Sum``), up-down counter (``Sum``,
  non-monotonic), manual histogram, observable gauge, plus the
  auto-instrumented ``http.client.duration`` histogram.
- **Logs** — log records with ``SeverityText``, ``Body``, and trace
  correlation (``trace_id`` / ``span_id`` embedded).

Injection mechanism
===================

Both scenarios use the PYTHONPATH + ``sitecustomize.py`` approach:

1. A ``prepare-python-agent`` Docker service installs all packages into
   ``./python-agent/``.
2. The app container mounts that directory and sets it on ``PYTHONPATH``.
3. Python automatically executes ``sitecustomize.py`` before any user code,
   which wires up the SDK and exporters.

The application source code (``app.py``) contains no OpenTelemetry imports.

Prerequisites
=============

- Docker with the Compose plugin (``docker compose``)
- The ``opentelemetry-python`` repository checked out locally at the path
  referenced in ``pyprotobuf/docker-compose.yml`` (required by the
  ``pyprotobuf`` scenario only; ``protobuf`` installs entirely from PyPI)

Running the pyprotobuf scenario
================================

::

    cd pyprotobuf
    docker compose up

Expected collector output::

    Traces   resource spans: ...  spans per batch: ...
    Span #N  Name: process_request  Kind: Internal  Status code: Ok
    Span #N  Name: GET              Kind: Client    Status code: Unset

    Logs     log records: ...
    Body: Str(request completed)  SeverityText: INFO

    Metrics  metrics: 5
    Name: app.requests          DataType: Sum  IsMonotonic: true
    Name: app.active_requests   DataType: Sum  IsMonotonic: false
    Name: app.request_duration  DataType: Histogram
    Name: app.memory_usage      DataType: Gauge
    Name: http.client.duration  DataType: Histogram

Request index 9 targets an unreachable address intentionally, producing an
ERROR span with an ``exception`` event and full stacktrace.

Running the protobuf scenario
==============================

::

    cd protobuf
    docker compose up

The collector output is structurally identical to the ``pyprotobuf`` scenario.
The only differences are ``service.name: Str(protobuf-demo)`` vs
``Str(pyprotobuf-demo)`` and the agent startup message in the app container
logs.

Running both simultaneously
============================

Each scenario uses its own Docker network (named after the directory), so they
can run at the same time without port conflicts::

    docker compose -f pyprotobuf/docker-compose.yml up &
    docker compose -f protobuf/docker-compose.yml up &

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
