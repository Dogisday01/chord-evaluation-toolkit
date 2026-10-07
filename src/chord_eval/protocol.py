"""Shared, versioned scoring configuration for files and model adapters."""

PROTOCOL_ID = "major_minor_n_v1"
TIME_TOLERANCE = 1e-9


def protocol_record() -> dict:
    return {
        "id": PROTOCOL_ID,
        "alphabet": "explicit major/minor/no-chord; no inversions",
        "coverage": "strict continuous [0, T]",
        "weighting": "duration_seconds",
        "boundary_tolerance_seconds": TIME_TOLERANCE,
        "segmentation": "mir_eval overseg/underseg/min; merge adjacent equivalent chords",
    }
