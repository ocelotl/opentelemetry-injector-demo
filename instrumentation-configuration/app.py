"""Flask demo app — no OpenTelemetry imports.

Instrumentation is activated entirely via the declarative configuration file
(otel-config.yaml) without any changes to this source file.
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return "Hello from the instrumentation-configuration demo!\n"


@app.route("/items/<int:item_id>")
def get_item(item_id):
    return jsonify({"id": item_id, "name": f"item-{item_id}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
