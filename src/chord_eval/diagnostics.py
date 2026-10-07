"""Duration-based error explanations, chord confusions and segmentation."""

import math
from collections import defaultdict

import mir_eval
import numpy as np

PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def canonical_label(label: str) -> str:
    if label == "N":
        return label
    root, quality = label.split(":")
    return f"{PITCHES[mir_eval.chord.pitch_class_to_semitone(root)]}:{quality}"


def change_intervals(annotation) -> np.ndarray:
    """Repeated equivalent labels are one chord, regardless of file row count."""
    rows = []
    last_label = None
    for item in annotation.segments:
        label = canonical_label(item.label)
        if label == last_label:
            rows[-1][1] = item.end
        else:
            rows.append([item.start, item.end])
        last_label = label
    return np.array(rows)


def diagnose(result: dict) -> dict:
    categories = defaultdict(list)
    cells = defaultdict(list)
    regions = []
    for segment in result["aligned_segments"]:
        ref = canonical_label(segment["reference"])
        pred = canonical_label(segment["prediction"])
        start, end = segment["start"], segment["end"]
        duration = end - start
        cells[ref, pred].append(duration)
        if segment["major_minor_match"] == 1:
            continue
        if ref == "N":
            category = "false_chord"
        elif pred == "N":
            category = "missed_chord"
        elif segment["root_match"] == 0:
            category = "wrong_root"
        else:
            category = "wrong_quality"
        categories[category].append(duration)
        if (
            regions
            and regions[-1]["end"] == start
            and (regions[-1]["reference"], regions[-1]["prediction"], regions[-1]["category"])
            == (ref, pred, category)
        ):
            regions[-1]["end"] = end
            regions[-1]["duration_seconds"] = end - regions[-1]["start"]
        else:
            regions.append(
                dict(
                    start=start,
                    end=end,
                    duration_seconds=duration,
                    reference=ref,
                    prediction=pred,
                    category=category,
                )
            )
    confusion = [
        dict(reference=ref, prediction=pred, seconds=math.fsum(durations))
        for (ref, pred), durations in sorted(cells.items())
    ]
    per_chord = []
    for label in sorted({ref for ref, _ in cells} | {pred for _, pred in cells}):
        support = math.fsum(c["seconds"] for c in confusion if c["reference"] == label)
        correct = math.fsum(
            c["seconds"] for c in confusion if c["reference"] == label and c["prediction"] == label
        )
        predicted = math.fsum(c["seconds"] for c in confusion if c["prediction"] == label)
        per_chord.append(
            dict(
                label=label,
                reference_seconds=support,
                predicted_seconds=predicted,
                correct_seconds=correct,
                recall=correct / support if support else None,
            )
        )
    ref_intervals = change_intervals(result["reference"])
    pred_intervals = change_intervals(result["prediction"])
    over = float(mir_eval.chord.overseg(ref_intervals, pred_intervals))
    under = float(mir_eval.chord.underseg(ref_intervals, pred_intervals))
    return {
        "error_seconds": {
            name: math.fsum(categories[name])
            for name in ("wrong_root", "wrong_quality", "missed_chord", "false_chord")
        },
        "error_regions": regions,
        "longest_errors": sorted(regions, key=lambda r: (-r["duration_seconds"], r["start"]))[:10],
        "confusion_seconds": confusion,
        "per_chord": per_chord,
        "segmentation": {"overseg": over, "underseg": under, "seg": min(over, under)},
    }
