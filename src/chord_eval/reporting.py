"""Portable provenance and complete, non-overwriting report publication."""

import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .validation import TIME_TOLERANCE


def build_report(result: dict, code_revision: str | None = None) -> dict:
    inputs = {}
    for role in ("reference", "prediction"):
        item = result[role]
        inputs[role] = {
            "name": item.name,
            "sha256": item.sha256,
            "interval_count": len(item.segments),
            "boundary_adjustments": list(item.adjustments),
        }
    return {
        "schema_version": "1.0",
        "tool": {
            "name": "chord-evaluation-toolkit",
            "version": __version__,
            "code_revision": code_revision,
        },
        "environment": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("mir_eval", "numpy", "scipy", "decorator")},
        },
        "protocol": {
            "alphabet": "explicit major/minor/no-chord; no inversions",
            "coverage": "strict continuous [0, T]",
            "weighting": "duration_seconds",
            "boundary_tolerance_seconds": TIME_TOLERANCE,
        },
        "inputs": inputs,
        "duration_seconds": result["duration_seconds"],
        "metrics": result["metrics"],
        "aligned_segments": result["aligned_segments"],
        "run": {"created_at_utc": datetime.now(timezone.utc).isoformat()},
    }


def write_report(report: dict, path: str | Path) -> None:
    """Stage complete bytes then create the target atomically without overwriting.

    The staging file is in the destination filesystem. A hard link publishes
    complete bytes with create-if-absent semantics (NTFS and Linux supported).
    Unsupported filesystems fail explicitly; no partial target is written.
    """
    target = Path(path)
    payload = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".chord-eval-", delete=False
        ) as f:
            temporary = Path(f.name)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
