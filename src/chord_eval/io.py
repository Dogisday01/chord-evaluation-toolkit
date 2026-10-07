"""Read one byte snapshot for both parsing and its reproducibility digest."""

import hashlib
from pathlib import Path

from .models import Annotation, AnnotationError, Segment
from .validation import validate_segments


def load_annotation(path: str | Path) -> Annotation:
    source = Path(path)
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AnnotationError(f"{source.name}: expected UTF-8 text") from exc
    segments = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 3:
            raise AnnotationError(f"{source.name}: line {number}: expected start end label")
        try:
            start, end = float(fields[0]), float(fields[1])
        except ValueError as exc:
            raise AnnotationError(f"{source.name}: line {number}: invalid numeric time") from exc
        segments.append(Segment(start, end, fields[2], number))
    normalized, adjustments = validate_segments(segments, source.name)
    return Annotation(source.name, hashlib.sha256(raw).hexdigest(), normalized, adjustments)
