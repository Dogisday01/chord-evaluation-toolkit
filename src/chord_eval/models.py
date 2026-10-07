"""Immutable input snapshots and explicit domain errors."""

from dataclasses import dataclass


class AnnotationError(ValueError):
    """An input violates the documented evaluation contract."""


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    label: str
    line: int


@dataclass(frozen=True)
class Annotation:
    name: str
    sha256: str
    segments: tuple[Segment, ...]
    adjustments: tuple[dict, ...]

    @property
    def duration(self) -> float:
        return self.segments[-1].end
