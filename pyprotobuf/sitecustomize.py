"""OTel bootstrap injected via the OpenTelemetry Injector (LD_PRELOAD).

Configures the OpenTelemetry SDK with the pyproto OTLP HTTP exporter — a
pure-Python protobuf encoder with NO dependency on google.protobuf.
"""

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from opentelemetry.exporter.otlp.pyproto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.pyproto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.pyproto.http.metric_exporter import OTLPMetricExporter

resource = Resource.create({"service.name": "pyprotobuf-demo"})

# Traces
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# Logs
logs_provider = LoggerProvider(resource=resource)
logs_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
set_logger_provider(logs_provider)

# Metrics
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(),
    export_interval_millis=5000,
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

RequestsInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)

print("agent: pyprotobuf OTLP HTTP exporter configured (no google.protobuf)", flush=True)
