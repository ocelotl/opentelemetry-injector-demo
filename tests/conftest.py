"""
Session-scoped fixture that either runs the Docker scenarios (default) or
points at an existing output directory (--no-docker).

Docker output lands in <repo>/compare-output/ because the collector volumes
in docker-compose.yml are hardcoded to ../compare-output/{scenario}/.
"""

from os import makedirs, chmod, getuid, getgid, environ
from os.path import exists, join, dirname, abspath
from shutil import rmtree
from subprocess import run
from time import sleep

from pytest import fixture

REPO = dirname(dirname(abspath(__file__)))
DEFAULT_OUT = join(REPO, "compare-output")


def pytest_addoption(parser):
    parser.addoption(
        "--no-docker",
        action="store_true",
        default=False,
        help=(
            "Skip running Docker scenarios and use the existing files in "
            "compare-output/ (or --output-dir if given). Useful for iterating "
            "on the test logic without re-running the full Docker stack."
        ),
    )
    parser.addoption(
        "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            "Path to a directory containing pyprotobuf/ and protobuf/ "
            "subdirectories with signal files. Implies --no-docker."
        ),
    )


def _compose_env() -> dict:
    return {**environ, "SCRIPT_UID": str(getuid()), "SCRIPT_GID": str(getgid())}


def _run_scenario(name: str, scenario_dir: str) -> None:
    compose_file = join(scenario_dir, "docker-compose.yml")
    env = _compose_env()
    run(["docker", "compose", "-f", compose_file, "up", "--detach"], check=True, env=env)
    run(["docker", "compose", "-f", compose_file, "wait", "app"], check=True, env=env)
    # Give the collector a moment to flush file exports after the app's final
    # SDK force_flush completes.
    sleep(3)
    run(["docker", "compose", "-f", compose_file, "down", "--timeout", "10"], check=True, env=env)


@fixture(scope="session")
def signal_dirs(request):
    """
    Returns {"pyprotobuf": "<path>", "protobuf": "<path>"} pointing at
    directories that each contain traces.json, metrics.json, logs.json.

    With --no-docker the directories are the existing compare-output/*
    subdirectories. Without the flag the scenarios are re-run first.
    """
    output_dir = request.config.getoption("--output-dir")
    if output_dir or request.config.getoption("--no-docker"):
        base = output_dir or DEFAULT_OUT
        return {
            "pyprotobuf": join(base, "pyprotobuf"),
            "protobuf": join(base, "protobuf"),
        }

    # Tear down any stale containers BEFORE deleting the output directory.
    # If a collector container from a prior run is still alive it holds a
    # bind-mount to the old directory inode; deleting and recreating the
    # directory creates a new inode the container doesn't know about, so
    # writes would silently go to the orphaned inode.
    env = _compose_env()
    for scenario in ("pyprotobuf", "protobuf"):
        run(
            ["docker", "compose", "-f", join(REPO, scenario, "docker-compose.yml"),
             "down", "--timeout", "10"],
            env=env,
        )

    # Clean and recreate output dirs; world-writable so the collector
    # container (uid 10001) can write the signal files into them.
    if exists(DEFAULT_OUT):
        rmtree(DEFAULT_OUT)
    for scenario in ("pyprotobuf", "protobuf"):
        makedirs(join(DEFAULT_OUT, scenario))
        chmod(join(DEFAULT_OUT, scenario), 0o777)  # bypass umask; collector runs as uid 10001
        # Pre-create the python-agent dir as the host user so Docker
        # bind-mounts don't recreate it as root.
        makedirs(join(REPO, scenario, "python-agent"), exist_ok=True)

    _run_scenario("pyprotobuf", join(REPO, "pyprotobuf"))
    _run_scenario("protobuf", join(REPO, "protobuf"))

    return {
        "pyprotobuf": join(DEFAULT_OUT, "pyprotobuf"),
        "protobuf": join(DEFAULT_OUT, "protobuf"),
    }
