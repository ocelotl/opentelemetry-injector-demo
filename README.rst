====================
OTel Injector Demo
====================

Overview
========

This project demonstrates a minimal OpenTelemetry auto-instrumentation setup
using an OpenTelemetry Collector and a Node.js HTTP application.

The purpose of this demo is to prove that telemetry can be injected into an
application automatically and exported successfully without modifying the
application code itself.

The telemetry flow looks like this:

::

    +-------------------+
    | Node.js App       |
    | (HTTP server)     |
    +-------------------+
              |
              | OpenTelemetry spans
              v
    +-------------------+
    | OTel Injector     |
    | Auto-Instrument.  |
    +-------------------+
              |
              | OTLP
              v
    +-------------------+
    | OTel Collector    |
    +-------------------+
              |
              | Debug Exporter
              v
    +-------------------+
    | Collector Logs    |
    +-------------------+

This demo proves that:

- The application is being instrumented successfully
- Traces are being generated automatically
- Telemetry reaches the Collector
- The Collector processes telemetry correctly
- Exporters can emit the telemetry successfully

No tracing logic exists in the application source code.

The telemetry is injected externally.

Project Structure
=================

This repository contains the following files:

::

    .
    ├── app.js
    ├── package.json
    ├── docker-compose.yml
    └── collector-config.yaml

Component Breakdown
===================

app.js
======

This is a minimal Node.js HTTP server.

Source:

::

    const http = require("http");

    const server = http.createServer((req, res) => {
      console.log("received request");

      res.end("hello from otel injector\\n");
    });

    server.listen(3000, () => {
      console.log("listening on port 3000");
    });

What this application does
--------------------------

- Creates a simple HTTP server
- Listens on port 3000
- Prints a message whenever a request arrives
- Returns a plain text response

Important observation
---------------------

The application contains:

- No OpenTelemetry SDK imports
- No tracing code
- No span creation
- No telemetry logic

This is critical.

If traces appear later in the Collector logs, then the instrumentation was
added externally by the injector.

That is the entire point of this demo.

package.json
============

Minimal Node.js metadata file:

::

    {
      "name": "otel-injector-demo",
      "version": "1.0.0"
    }

This exists primarily so the Node.js environment behaves like a normal Node
project.

collector-config.yaml
=====================

This file configures the OpenTelemetry Collector.

The Collector acts as a telemetry router.

Telemetry flow inside the Collector:

::

    receivers -> processors -> exporters

Receivers
---------

The Collector receives telemetry using OTLP.

Supported protocols:

- OTLP/gRPC on port 4317
- OTLP/HTTP on port 4318

Processors
----------

The batch processor groups spans together before export.

This improves efficiency and reflects production best practices.

Exporters
---------

The debug exporter prints telemetry directly to Collector logs.

This is ideal for educational purposes because we can inspect the raw spans.

docker-compose.yml
==================

Docker Compose orchestrates the containers involved in the demo.

Typical architecture:

::

    +---------------------+
    | app container       |
    +---------------------+

    +---------------------+
    | collector container |
    +---------------------+

Docker networking allows the application container to send telemetry to the
Collector container.

Why Containers Matter
=====================

Containers provide:

- Process isolation
- Reproducibility
- Stable networking
- Portable environments

This makes the demo deterministic and easy to reproduce.

OpenTelemetry Concepts
======================

What is OpenTelemetry?
======================

OpenTelemetry is a standard for observability telemetry.

It provides:

- Traces
- Metrics
- Logs
- Context propagation
- Instrumentation libraries

What is a Trace?
================

A trace represents the lifecycle of a request or operation.

Example:

::

    Incoming HTTP Request
        |
        +-- Database Query
        |
        +-- API Call
        |
        +-- Cache Access

Each operation inside a trace is represented by a span.

What is a Span?
===============

A span is a timed operation.

A span contains:

- Start time
- End time
- Attributes
- Events
- Parent-child relationships

Example:

::

    Span: HTTP GET /users

Attributes might include:

::

    http.method = GET
    http.route = /users
    http.status_code = 200

What is Auto-Instrumentation?
=============================

Auto-instrumentation means telemetry is added automatically without modifying
application code.

Normally developers would manually write code like:

::

    const span = tracer.startSpan("operation");

Auto-instrumentation avoids that.

Instead:

- A runtime hook
- Monkey patching
- eBPF
- Loader injection
- Environment configuration

automatically instruments frameworks and libraries.

In this demo, the injector instruments the Node.js HTTP server automatically.

Why This Demo Matters
=====================

This project demonstrates something extremely important:

The application itself has NO telemetry code.

Yet spans still appear.

That proves:

- Instrumentation was injected externally
- The injector works
- OpenTelemetry hooks are functioning
- Telemetry export is functioning

This is the core value proposition of instrumentation injectors.

How the Demo Works Internally
=============================

Step 1
======

The Node.js app starts.

It only creates an HTTP server.

No telemetry exists yet.

Step 2
======

The injector modifies runtime behavior.

This usually happens through:

- preload hooks
- runtime patching
- environment variables
- wrapper processes
- injected SDK initialization

The injector activates OpenTelemetry instrumentation.

Step 3
======

The HTTP library becomes instrumented automatically.

When requests arrive:

- spans are created
- context is propagated
- metadata is attached

Step 4
======

Telemetry is exported using OTLP.

The app sends spans to the Collector.

Step 5
======

The Collector receives telemetry.

The Collector then:

- batches spans
- processes spans
- exports spans

Step 6
======

The debug exporter prints the spans.

Example output:

::

    Resource attributes:
         -> service.name: Str(otel-injector-demo)

This proves the telemetry pipeline is functioning correctly.

How to Run
===========

Start the containers:

::

    docker compose up

You should see logs indicating:

::

    listening on port 3000

and:

::

    Everything is ready

Generate traffic
================

Send a request to the application:

::

    curl http://localhost:3000

Expected response:

::

    hello from otel injector

Observe Collector Logs
======================

The Collector should print spans similar to:

::

    Traces
    ResourceSpans #0

    -> service.name: Str(otel-injector-demo)

This is the key proof.

Why This Output Matters
=======================

The Node.js application never created spans manually.

Yet the Collector received spans.

Therefore:

- auto-instrumentation succeeded
- telemetry injection succeeded
- export succeeded

This demonstrates a working instrumentation pipeline.

What the Collector Output Shows
================================

service.name
------------

::

    service.name: Str(otel-injector-demo)

This identifies the service producing telemetry.

process.pid
-----------

::

    process.pid: Int(...)

The process ID of the instrumented application.

process.command_args
--------------------

Shows the command used to launch the process.

This proves the runtime process itself was instrumented.

Span Data
---------

The spans themselves prove that:

- HTTP requests were intercepted
- timing information was collected
- instrumentation hooks executed correctly

How Real Systems Extend This
============================

Real production systems usually replace the debug exporter with:

- Jaeger
- Tempo
- Datadog
- Honeycomb
- New Relic
- Grafana Cloud

Additional processors are often added:

- sampling
- attribute filtering
- Kubernetes enrichment
- tail sampling
- memory limiting

The same architecture scales to large distributed systems.

Key Takeaways
=============

This demo proves that:

- Applications can be instrumented externally
- Telemetry can be collected automatically
- OpenTelemetry Collector pipelines work
- OTLP transport works
- The injector successfully activates instrumentation
- No application tracing code is required

This is the foundation of modern observability platforms.
