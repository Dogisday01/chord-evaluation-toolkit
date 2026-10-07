"""Portable provenance and complete, non-overwriting report publication."""

import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .analysis import analyze
from .diagnostics import diagnose
from .protocol import protocol_record


def environment_record() -> dict:
    return {
        "python": platform.python_version(),
        **{name: version(name) for name in ("mir_eval", "numpy", "scipy", "decorator")},
    }


def build_report(result: dict, code_revision: str | None = None) -> dict:
    inputs = {}
    for role in ("reference", "prediction"):
        item = result[role]
        inputs[role] = {
            "name": item.name,
            "sha256": item.sha256,
            "hash_representation": item.hash_representation,
            "interval_count": len(item.segments),
            "boundary_adjustments": list(item.adjustments),
        }
    diagnostics = diagnose(result)
    return {
        "schema_version": "1.2",
        "kind": "pair",
        "tool": {
            "name": "chord-evaluation-toolkit",
            "version": __version__,
            "code_revision": code_revision,
        },
        "environment": environment_record(),
        "protocol": protocol_record(),
        "inputs": inputs,
        "duration_seconds": result["duration_seconds"],
        "metrics": result["metrics"],
        "aligned_segments": result["aligned_segments"],
        "diagnostics": diagnostics,
        "analysis": analyze(result, diagnostics),
        "run": {"created_at_utc": datetime.now(timezone.utc).isoformat()},
    }


def write_report(report: dict, path: str | Path) -> None:
    """Stage complete bytes then create the target atomically without overwriting.

    The staging file is in the destination filesystem. A hard link publishes
    complete bytes with create-if-absent semantics (NTFS and Linux supported).
    Unsupported filesystems fail explicitly; no partial target is written.
    """
    payload = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
    write_outputs({Path(path): payload})


def write_outputs(outputs: dict[Path, bytes]) -> None:
    """Publish complete files; roll back this operation's outputs on failure.

    Each file is published atomically, not a multi-filesystem transaction. A
    process interruption can leave a subset. Existing files are never replaced.
    """
    resolved = [p.resolve() for p in outputs]
    if len(set(resolved)) != len(resolved):
        raise OSError("JSON and HTML outputs must be different paths")
    staged, created = [], []
    try:
        for target, payload in outputs.items():
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".chord-eval-", delete=False
            ) as f:
                temporary = Path(f.name)
                staged.append((target, temporary))
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        for target, temporary in staged:
            os.link(temporary, target)
            created.append((target, temporary))
    except OSError:
        for target, temporary in reversed(created):
            if target.exists() and target.samefile(temporary):
                target.unlink()
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)
