"""OTel SDK bootstrap injected via PYTHONPATH.

Loads the declarative configuration file and calls configure_sdk(), which:
  1. Creates the tracer/meter/logger providers from the YAML.
  2. Reads instrumentation/development.python and calls
     FlaskInstrumentor().instrument() automatically — no explicit call here.

The application source (app.py) has zero OpenTelemetry imports.
"""

import os

from opentelemetry.sdk._configuration.file._loader import load_config_file
from opentelemetry.sdk._configuration._sdk import configure_sdk

_config_path = os.environ.get("OTEL_CONFIG_FILE", "/app/otel-config.yaml")
configure_sdk(load_config_file(_config_path))

print(
    "sitecustomize: SDK configured from declarative config; "
    "Flask auto-instrumented via instrumentation/development.python.flask",
    flush=True,
)
