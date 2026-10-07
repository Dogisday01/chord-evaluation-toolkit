"""Strict chronology and alphabet checks, before any metric is computed."""

import math
import re
from dataclasses import replace

import mir_eval

from .models import AnnotationError, Segment
from .protocol import TIME_TOLERANCE

LABEL_PATTERN = re.compile(r"(?:[A-G](?:#|b)?:(?:maj|min)|N)\Z")


def validate_segments(
    segments: list[Segment], name: str
) -> tuple[tuple[Segment, ...], tuple[dict, ...]]:
    if not segments:
        raise AnnotationError(f"{name}: file has no intervals")
    normalized: list[Segment] = []
    adjustments: list[dict] = []
    for segment in segments:
        where = f"{name}: line {segment.line}"
        if not math.isfinite(segment.start) or not math.isfinite(segment.end):
            raise AnnotationError(f"{where}: times must be finite")
        if segment.start < 0 or segment.end <= segment.start:
            raise AnnotationError(f"{where}: require 0 <= start < end")
        if not LABEL_PATTERN.fullmatch(segment.label):
            raise AnnotationError(f"{where}: label must be ROOT:maj, ROOT:min, or N")
        try:
            mir_eval.chord.validate_chord_label(segment.label)
        except mir_eval.chord.InvalidChordException as exc:
            raise AnnotationError(f"{where}: invalid chord label {segment.label!r}") from exc
        expected = normalized[-1].end if normalized else 0.0
        delta = segment.start - expected
        if abs(delta) > TIME_TOLERANCE:
            reason = "gap" if delta > 0 else "overlap or unsorted intervals"
            if not normalized:
                reason = "timeline must start at zero"
            raise AnnotationError(f"{where}: {reason}")
        if segment.start != expected:
            adjustments.append(
                {"line": segment.line, "field": "start", "from": segment.start, "to": expected}
            )
            segment = replace(segment, start=expected)
        if segment.end <= segment.start:
            raise AnnotationError(f"{where}: rounding would collapse this interval")
        normalized.append(segment)
    return tuple(normalized), tuple(adjustments)
