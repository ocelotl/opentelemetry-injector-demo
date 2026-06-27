instrumentation-configuration demo
===================================

Demonstrates the ``instrumentation/development.python`` section of the
`OpenTelemetry declarative configuration schema`_.  A Flask application is
fully instrumented — producing HTTP trace spans, metrics, and logs — without
any OpenTelemetry import in its source code.  The SDK is configured and
``FlaskInstrumentor().instrument()`` is called automatically, driven entirely
by a YAML file.

.. _OpenTelemetry declarative configuration schema:
   https://opentelemetry.io/docs/specs/otel/configuration/


How it works
------------

1. ``otel-config.yaml`` contains an ``instrumentation/development.python``
   section::

       instrumentation/development:
         python:
           flask: {}

2. ``sitecustomize.py`` is placed in the venv's ``site-packages/`` directory.
   Python executes it automatically before any application code::

       configure_sdk(load_config_file(os.environ["OTEL_CONFIG_FILE"]))

3. ``configure_sdk()`` reads the ``instrumentation/development.python`` map,
   looks up each key in the ``opentelemetry_instrumentor`` entry-point group,
   and calls ``instrument()`` on the discovered class.

4. ``app.py`` has zero OpenTelemetry imports.  Instrumentation is injected
   from outside, exactly as a Kubernetes injector sidecar would do it.


Running the demo
----------------

Requires Docker with the Compose plugin.

.. code-block:: bash

    cd instrumentation-configuration

    # First run: builds the venv from GitHub (≈ 2 min)
    docker compose up

    # Subsequent runs reuse the cached venv
    docker compose up

To force a full rebuild (e.g. after pushing new commits to the pyproto branch):

.. code-block:: bash

    rm -rf python-agent && docker compose up


Inspecting the output
---------------------

After the traffic container exits, three JSONL files are written to
``output/``:

.. code-block:: bash

    # Number of trace spans (one per HTTP request)
    wc -l output/traces.jsonl

    # Pretty-print the first span
    python3 -c "import json; print(json.dumps(json.loads(open('output/traces.jsonl').readline()), indent=2))"

Each trace span has scope ``opentelemetry.instrumentation.flask`` and
``service.name: instrumentation-config-demo`` as set in ``otel-config.yaml``.


Files
-----

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Purpose
   * - ``otel-config.yaml``
     - Declarative SDK config.  Sets providers, exporters, propagators, and
       the ``instrumentation/development.python`` map.
   * - ``sitecustomize.py``
     - Bootstrap shim placed in ``site-packages/``.  Calls ``configure_sdk()``
       before application code runs.
   * - ``app.py``
     - Minimal Flask app.  Contains no OTel imports.
   * - ``traffic.py``
     - Sends four HTTP requests to generate span data.
   * - ``docker-compose.yml``
     - Three services: ``prepare-python-agent`` (venv builder),
       ``app`` (Flask), ``traffic`` (load generator).
   * - ``output/``
     - Written at runtime.  Contains ``traces.jsonl``, ``metrics.jsonl``,
       ``logs.jsonl``.


Implementation note
-------------------

The SDK implementation of ``configure_instrumentation()`` lives in
``opentelemetry-sdk/src/opentelemetry/sdk/_configuration/_instrumentation.py``
on the ``issue_5361`` branch of `ocelotl/opentelemetry-python`_.  This demo
installs that branch via the ``pyproto`` branch, which rebases the
``issue_5361`` changes on top of the pure-Python protobuf and JSON-file
exporter work.

.. _ocelotl/opentelemetry-python: https://github.com/ocelotl/opentelemetry-python
