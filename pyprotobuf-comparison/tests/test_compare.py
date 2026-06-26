"""
Verify that pyprotobuf and protobuf scenarios produce semantically identical
telemetry.  Each parametrized test covers one signal (traces / metrics / logs).

On failure the full unified diff of the normalized outputs is included in the
assertion message, mirroring the detail level of compare.sh's `diff` call.
"""

from difflib import unified_diff
from json import dumps
from os.path import exists, join

from pytest import fail, mark

from normalize import normalize_logs, normalize_metrics, normalize_traces

_NORMALIZERS = {
    "traces": normalize_traces,
    "metrics": normalize_metrics,
    "logs": normalize_logs,
}


@mark.parametrize("signal", ["traces", "metrics", "logs"])
def test_signal_match(signal, signal_dirs):
    py_path = join(signal_dirs["pyprotobuf"], f"{signal}.json")
    pb_path = join(signal_dirs["protobuf"], f"{signal}.json")

    missing = [p for p in (py_path, pb_path) if not exists(p)]
    if missing:
        fail(
            f"{signal}: output file(s) not found\n"
            + "\n".join(f"  {p}" for p in missing),
            pytrace=False,
        )

    normalize = _NORMALIZERS[signal]
    py_norm = normalize(py_path)
    pb_norm = normalize(pb_path)

    if py_norm == pb_norm:
        return

    py_lines = dumps(py_norm, indent=2).splitlines(keepends=True)
    pb_lines = dumps(pb_norm, indent=2).splitlines(keepends=True)

    diff = "".join(
        unified_diff(
            py_lines,
            pb_lines,
            fromfile=f"pyprotobuf/{signal}.json  (normalized)",
            tofile=f"protobuf/{signal}.json    (normalized)",
        )
    )
    fail(
        f"{signal}: normalized outputs differ\n\n{diff}",
        pytrace=False,
    )
