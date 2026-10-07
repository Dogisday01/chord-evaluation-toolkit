"""Explicit external-data projection, separate from the strict scoring protocol."""

import mir_eval

from .diagnostics import PITCHES
from .models import AnnotationError


def project_harte_label(label: str) -> str:
    """Discard extensions/bass only for one identifiable major or minor triad.

    This declared projection is not a reproduction of the official MIREX
    evaluation protocol. Unknown and unrepresentable labels are never N.
    """
    if label == "N":
        return "N"
    if label == "X":
        raise AnnotationError("unknown reference label X cannot be projected")
    try:
        root, pitches, _ = mir_eval.chord.encode(label)
    except (mir_eval.chord.InvalidChordException, ValueError) as exc:
        raise AnnotationError(f"invalid Harte label: {label}") from exc
    major = all(pitches[i] == 1 for i in (0, 4, 7))
    minor = all(pitches[i] == 1 for i in (0, 3, 7))
    if major == minor or not 0 <= root < 12:
        raise AnnotationError(f"no unique major/minor triad in {label}")
    return f"{PITCHES[root]}:{'maj' if major else 'min'}"


def crop_rows(rows: list[tuple], end: float) -> list[tuple]:
    """Explicit [0,end] excerpt from validated rows; no padding or time shift."""
    if not rows or not 0 < end <= rows[-1][1]:
        raise AnnotationError("excerpt end must be within supplied coverage")
    return [(start, min(stop, end), label) for start, stop, label in rows if start < end]
