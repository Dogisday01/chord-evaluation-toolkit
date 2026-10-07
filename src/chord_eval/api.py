"""Public adapter boundary for future model outputs, independent of audio code."""

import hashlib
import json
import math
from collections.abc import Iterable
from numbers import Real

from .collection import run_experiment
from .evaluation import score_annotations
from .io import load_annotation
from .models import Annotation, AnnotationError, Segment
from .reporting import build_report
from .validation import validate_segments

__all__ = ["annotation_from_intervals", "evaluate_intervals", "evaluate_files", "run_experiment"]


def annotation_from_intervals(
    intervals: Iterable[tuple[float, float, str]], name: str = "in_memory"
) -> Annotation:
    """Validate (start seconds, end seconds, label) rows and hash their snapshot."""
    if not isinstance(name, str) or not name:
        raise AnnotationError("annotation name must be a nonempty string")
    rows, segments = [], []
    try:
        for line, row in enumerate(intervals, 1):
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise AnnotationError(f"{name}: line {line}: expected start end label")
            start, end, label = row
            if (
                isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, Real)
                or not isinstance(end, Real)
                or not isinstance(label, str)
            ):
                raise AnnotationError(
                    f"{name}: line {line}: require numeric times and a string label"
                )
            start, end = float(start), float(end)
            if not math.isfinite(start) or not math.isfinite(end):
                raise AnnotationError(f"{name}: line {line}: times must be finite")
            rows.append([start, end, label])
            segments.append(Segment(start, end, label, line))
    except (TypeError, OverflowError) as exc:
        raise AnnotationError(f"{name}: expected finite interval rows") from exc
    normalized, changes = validate_segments(segments, name)
    snapshot = json.dumps(rows, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(snapshot.encode("ascii")).hexdigest()
    return Annotation(name, digest, normalized, changes, "canonical_interval_json_v1")


def evaluate_intervals(reference, prediction, *, code_revision: str | None = None) -> dict:
    """Return a report; validate both model adapter and reference inputs."""
    ref = annotation_from_intervals(reference, "reference")
    pred = annotation_from_intervals(prediction, "prediction")
    return build_report(score_annotations(ref, pred), code_revision)


def evaluate_files(reference, prediction, *, code_revision: str | None = None) -> dict:
    """The same protocol with original-file byte hashes."""
    return build_report(
        score_annotations(load_annotation(reference), load_annotation(prediction)), code_revision
    )
