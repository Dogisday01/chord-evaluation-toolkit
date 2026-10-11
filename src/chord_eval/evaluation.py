"""Align temporal boundaries and apply named mir_eval comparison rules."""

from dataclasses import replace

import mir_eval
import numpy as np

from .models import Annotation, AnnotationError
from .validation import TIME_TOLERANCE


def align_pair(reference: Annotation, prediction: Annotation) -> tuple[Annotation, Annotation]:
    if abs(reference.duration - prediction.duration) > TIME_TOLERANCE:
        raise AnnotationError("reference and prediction must cover the same [0, T] timeline")
    if reference.duration != prediction.duration:
        last = prediction.segments[-1]
        if reference.duration <= last.start:
            raise AnnotationError("endpoint rounding would collapse the prediction's last interval")
        adjustment = {"line": last.line, "field": "end", "from": last.end, "to": reference.duration}
        prediction = replace(
            prediction,
            segments=prediction.segments[:-1] + (replace(last, end=reference.duration),),
            adjustments=prediction.adjustments + (adjustment,),
        )
    return reference, prediction


def score_annotations(reference: Annotation, prediction: Annotation) -> dict:
    reference, prediction = align_pair(reference, prediction)
    ref_times = np.array([(s.start, s.end) for s in reference.segments])
    pred_times = np.array([(s.start, s.end) for s in prediction.segments])
    times, ref_labels, pred_labels = mir_eval.util.merge_labeled_intervals(
        ref_times,
        [s.label for s in reference.segments],
        pred_times,
        [s.label for s in prediction.segments],
    )
    durations = mir_eval.util.intervals_to_durations(times)
    comparisons = {
        "root": mir_eval.chord.root(ref_labels, pred_labels),
        "major_minor": mir_eval.chord.majmin(ref_labels, pred_labels),
    }
    scores = {}
    for name, values in comparisons.items():
        if not np.all(np.isfinite(values) & (values >= 0) & (values <= 1)):
            raise AnnotationError(f"{name}: unexpected comparison outside the accepted alphabet")
        scores[name] = float(mir_eval.chord.weighted_accuracy(values, durations))
    segments = [
        {
            "start": float(start),
            "end": float(end),
            "reference": ref,
            "prediction": pred,
            "root_match": float(comparisons["root"][i]),
            "major_minor_match": float(comparisons["major_minor"][i]),
        }
        for i, ((start, end), ref, pred) in enumerate(zip(times, ref_labels, pred_labels))
    ]
    return {
        "metrics": scores,
        "duration_seconds": reference.duration,
        "aligned_segments": segments,
        "reference": reference,
        "prediction": prediction,
    }
