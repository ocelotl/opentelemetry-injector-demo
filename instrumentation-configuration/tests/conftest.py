"""Session-scoped fixture that runs the Docker Compose stack and returns the
path to the output directory containing the JSONL telemetry files."""

from os import makedirs, chmod, getuid, getgid, environ
from os.path import exists, join, dirname, abspath
from shutil import rmtree
from subprocess import run

from pytest import fixture

DEMO_DIR = dirname(dirname(abspath(__file__)))
OUTPUT_DIR = join(DEMO_DIR, "output")
COMPOSE_FILE = join(DEMO_DIR, "docker-compose.yml")


def pytest_addoption(parser):
    parser.addoption(
        "--no-docker",
        action="store_true",
        default=False,
        help="Skip Docker; use the existing output/ directory.",
    )


def _env() -> dict:
    return {**environ, "SCRIPT_UID": str(getuid()), "SCRIPT_GID": str(getgid())}


@fixture(scope="session")
def output_dir(request):
    """Run the full Docker Compose stack and return the output directory path.

    With --no-docker the existing output/ directory is used as-is.
    """
    if request.config.getoption("--no-docker"):
        return OUTPUT_DIR

    env = _env()

    # Tear down stale containers first.
    run(
        ["docker", "compose", "-f", COMPOSE_FILE, "down", "--timeout", "10"],
        env=env,
    )

    # Clean output directory and recreate it world-writable.
    if exists(OUTPUT_DIR):
        rmtree(OUTPUT_DIR)
    makedirs(OUTPUT_DIR)
    chmod(OUTPUT_DIR, 0o777)

    makedirs(join(DEMO_DIR, "python-agent"), exist_ok=True)

    # Run the stack: prepare-python-agent → app + traffic.
    run(
        ["docker", "compose", "-f", COMPOSE_FILE, "up", "--detach"],
        check=True,
        env=env,
    )
    # Wait for the traffic generator to finish (it exits after sending requests).
    run(
        ["docker", "compose", "-f", COMPOSE_FILE, "wait", "traffic"],
        check=True,
        env=env,
    )
    # Brief pause so the app flushes the last spans to disk before we read.
    from time import sleep
    sleep(2)
    run(
        ["docker", "compose", "-f", COMPOSE_FILE, "down", "--timeout", "10"],
        check=True,
        env=env,
    )

    return OUTPUT_DIR
