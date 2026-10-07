"""One manifest fixes comparable records, references, models and protocol."""

import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from . import __version__
from .evaluation import score_annotations
from .io import load_annotation
from .models import AnnotationError
from .protocol import PROTOCOL_ID, protocol_record
from .reporting import build_report, environment_record

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
METRICS = ("root", "major_minor")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AnnotationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise AnnotationError(f"nonfinite JSON value: {value}")


def keys(value, required, optional, context):
    if not isinstance(value, dict):
        raise AnnotationError(f"{context}: expected an object")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise AnnotationError(
            f"{context}: missing keys {sorted(missing)}; unknown {sorted(unknown)}"
        )


def identifier(value, context):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise AnnotationError(
            f"{context}: use a 1-64 character ID containing letters, digits, ._- "
        )


def load_manifest(path: str | Path) -> tuple[dict, str]:
    source = Path(path)
    raw = source.read_bytes()
    try:
        data = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AnnotationError(f"{source.name}: expected valid UTF-8 JSON") from exc
    keys(
        data,
        ("schema_version", "dataset_id", "split", "protocol_id", "models", "tracks"),
        ("data_provenance",),
        "manifest",
    )
    if data["schema_version"] != "1.0" or data["protocol_id"] != PROTOCOL_ID:
        raise AnnotationError("manifest: unsupported schema or evaluation protocol")
    identifier(data["dataset_id"], "dataset_id")
    if data["split"] not in ("train", "validation", "test"):
        raise AnnotationError("manifest: split must be train, validation or test")
    if "data_provenance" in data:
        provenance = data["data_provenance"]
        keys(
            provenance,
            (),
            ("source", "source_revision", "preparation", "audit_file", "selection"),
            "data_provenance",
        )
        if any(not isinstance(value, str) for value in provenance.values()):
            raise AnnotationError("data_provenance: all values must be strings")
    models = data["models"]
    if not isinstance(models, dict) or not models:
        raise AnnotationError("manifest: declare at least one model")
    for model, metadata in models.items():
        identifier(model, "model")
        keys(
            metadata,
            (),
            ("description", "checkpoint_sha256", "configuration_sha256", "seed", "code_revision"),
            f"model {model}",
        )
        for field in ("checkpoint_sha256", "configuration_sha256"):
            if field in metadata and (
                not isinstance(metadata[field], str)
                or not re.fullmatch(r"[0-9a-f]{64}", metadata[field])
            ):
                raise AnnotationError(f"model {model}: {field} must be a lowercase SHA-256")
        if "seed" in metadata and (
            isinstance(metadata["seed"], bool) or not isinstance(metadata["seed"], int)
        ):
            raise AnnotationError(f"model {model}: seed must be an integer")
        for field in ("description", "code_revision"):
            if field in metadata and not isinstance(metadata[field], str):
                raise AnnotationError(f"model {model}: {field} must be a string")
    if not isinstance(data["tracks"], list) or not data["tracks"]:
        raise AnnotationError("manifest: declare at least one track")
    seen = set()
    for track in data["tracks"]:
        keys(track, ("id", "reference", "predictions"), (), "track")
        identifier(track["id"], "track")
        if track["id"] in seen:
            raise AnnotationError(f"duplicate track ID: {track['id']}")
        seen.add(track["id"])
        predictions = track["predictions"]
        if not isinstance(predictions, dict) or predictions.keys() != models.keys():
            raise AnnotationError(f"track {track['id']}: predictions must match declared models")
        for filename in [track["reference"], *predictions.values()]:
            if not isinstance(filename, str) or not filename.strip() or "\0" in filename:
                raise AnnotationError(f"track {track['id']}: require nonempty file paths")
    return data, hashlib.sha256(raw).hexdigest()


def aggregate(reports: list[dict]) -> dict:
    duration = math.fsum(r["duration_seconds"] for r in reports)
    patterns = defaultdict(list)
    for report in reports:
        for item in report["analysis"]["confusion_patterns"]:
            patterns[item["reference"], item["prediction"]].append(item)
    pooled = sorted(
        [
            dict(
                reference=ref,
                prediction=pred,
                seconds=math.fsum(i["seconds"] for i in items),
                occurrences=sum(i["occurrences"] for i in items),
                recording_count=len(items),
            )
            for (ref, pred), items in patterns.items()
        ],
        key=lambda item: (-item["seconds"], item["reference"], item["prediction"]),
    )
    return {
        "track_count": len(reports),
        "duration_seconds": duration,
        "macro": {m: math.fsum(r["metrics"][m] for r in reports) / len(reports) for m in METRICS},
        "micro": {
            m: math.fsum(r["metrics"][m] * r["duration_seconds"] for r in reports) / duration
            for m in METRICS
        },
        "analysis": {
            "error_seconds": {
                name: math.fsum(r["diagnostics"]["error_seconds"][name] for r in reports)
                for name in ("wrong_root", "wrong_quality", "missed_chord", "false_chord")
            },
            "metrics_distribution": {
                metric: dict(
                    minimum=min(r["metrics"][metric] for r in reports),
                    maximum=max(r["metrics"][metric] for r in reports),
                    median=median(r["metrics"][metric] for r in reports),
                )
                for metric in METRICS
            },
            "confusion_patterns": pooled,
        },
    }


def compare_records(records, summaries, baseline, candidate):
    changes = []
    counts = {m: dict(improved=0, worsened=0, tied=0) for m in METRICS}
    for record in records:
        a = record["evaluations"][baseline]["metrics"]
        b = record["evaluations"][candidate]["metrics"]
        delta = {m: b[m] - a[m] for m in METRICS}
        for metric, value in delta.items():
            outcome = "tied" if abs(value) <= 1e-12 else "improved" if value > 0 else "worsened"
            counts[metric][outcome] += 1
        changes.append(dict(track_id=record["id"], delta=delta))
    return {
        "baseline": baseline,
        "candidate": candidate,
        "direction": "candidate_minus_baseline",
        "delta_unit": "score; multiply by 100 for percentage points",
        "aggregate_delta": {
            weighting: {
                m: summaries[candidate][weighting][m] - summaries[baseline][weighting][m]
                for m in METRICS
            }
            for weighting in ("macro", "micro")
        },
        "track_changes": changes,
        "outcomes": counts,
        "interpretation": "descriptive paired comparison; no statistical significance claim",
    }


def run_experiment(manifest_path, *, baseline=None, candidate=None, code_revision=None) -> dict:
    """Evaluate all declared models. Incomplete collections have no aggregate."""
    manifest, digest = load_manifest(manifest_path)
    if (baseline is None) != (candidate is None):
        raise AnnotationError("comparison requires both baseline and candidate")
    if baseline is not None and (
        baseline == candidate
        or baseline not in manifest["models"]
        or candidate not in manifest["models"]
    ):
        raise AnnotationError("choose two distinct declared model IDs")
    parent = Path(manifest_path).resolve().parent
    snapshots, records = {}, []

    def read(filename):
        path = (parent / filename).resolve()
        if path not in snapshots:
            try:
                snapshots[path] = load_annotation(path)
            except AnnotationError as exc:
                snapshots[path] = str(exc)
            except OSError as exc:
                snapshots[path] = f"{path.name}: {exc.strerror or type(exc).__name__}"
        return snapshots[path]

    for track in manifest["tracks"]:
        ref = read(track["reference"])
        reports, errors = {}, []
        if isinstance(ref, str):
            errors.append(dict(role="reference", message=ref))
        for model, filename in track["predictions"].items():
            pred = read(filename)
            if isinstance(pred, str):
                errors.append(dict(role="prediction", model=model, message=pred))
            elif not isinstance(ref, str):
                try:
                    reports[model] = build_report(score_annotations(ref, pred), code_revision)
                except AnnotationError as exc:
                    errors.append(dict(role="prediction", model=model, message=str(exc)))
        records.append(
            dict(
                id=track["id"],
                status="invalid" if errors else "valid",
                evaluations=reports,
                errors=errors,
            )
        )
    complete = all(r["status"] == "valid" for r in records)
    summaries = (
        {
            model: aggregate([r["evaluations"][model] for r in records])
            for model in manifest["models"]
        }
        if complete
        else None
    )
    comparison = (
        compare_records(records, summaries, baseline, candidate)
        if complete and baseline is not None
        else None
    )
    return {
        "schema_version": "1.2",
        "kind": "collection",
        "status": "complete" if complete else "incomplete",
        "tool": dict(
            name="chord-evaluation-toolkit", version=__version__, code_revision=code_revision
        ),
        "environment": environment_record(),
        "protocol": protocol_record(),
        "manifest": dict(
            name=Path(manifest_path).name, sha256=digest, schema_version=manifest["schema_version"]
        ),
        "dataset": dict(id=manifest["dataset_id"], split=manifest["split"]),
        "data_provenance": manifest.get("data_provenance"),
        "models": manifest["models"],
        "records": records,
        "summary": summaries,
        "comparison": comparison,
        "aggregation_policy": "all declared tracks and models must be valid; otherwise unavailable",
        "run": dict(created_at_utc=datetime.now(timezone.utc).isoformat()),
    }
