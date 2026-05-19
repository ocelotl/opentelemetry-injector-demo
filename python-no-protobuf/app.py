from sys import stderr

from flask import Flask

app = Flask(__name__)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def hello(path: str) -> tuple[str, int, dict[str, str]]:
    print("received request", flush=True, file=stderr)
    return "hello from otel injector\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    print("listening on port 3000", flush=True, file=stderr)
    app.run(host="0.0.0.0", port=3000)
