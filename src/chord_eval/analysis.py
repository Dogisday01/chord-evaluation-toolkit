"""Auditable descriptive patterns over already aligned, validated annotations."""

import math
from collections import defaultdict
from statistics import median

from .diagnostics import PITCHES, canonical_label

BOUNDARY_RADIUS = 0.25
BIN_COUNT = 10


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def overlap(start, end, left, right):
    return max(0.0, min(end, right) - max(start, left))


def analyze(result: dict, diagnostics: dict) -> dict:
    segments = result["aligned_segments"]
    duration = result["duration_seconds"]
    error_time = math.fsum(diagnostics["error_seconds"].values())
    episodes = []
    for segment in segments:
        if segment["major_minor_match"] == 1:
            continue
        start, end = segment["start"], segment["end"]
        if episodes and episodes[-1]["end"] == start:
            episodes[-1]["end"] = end
            episodes[-1]["duration_seconds"] = end - episodes[-1]["start"]
        else:
            episodes.append(dict(start=start, end=end, duration_seconds=end - start))
    lengths = [e["duration_seconds"] for e in episodes]
    summary = dict(
        error_seconds=error_time,
        error_fraction=error_time / duration,
        episode_count=len(episodes),
        mean_episode_seconds=ratio(math.fsum(lengths), len(lengths)),
        median_episode_seconds=median(lengths) if lengths else None,
        longest_episode=max(episodes, key=lambda e: e["duration_seconds"]) if episodes else None,
    )
    by_pair = defaultdict(list)
    offsets = defaultdict(list)
    for region in diagnostics["error_regions"]:
        by_pair[region["reference"], region["prediction"]].append(region["duration_seconds"])
        if region["category"] == "wrong_root":
            ref = PITCHES.index(region["reference"].split(":")[0])
            pred = PITCHES.index(region["prediction"].split(":")[0])
            offsets[(pred - ref) % 12].append(region["duration_seconds"])
    patterns = sorted(
        [
            dict(
                reference=ref,
                prediction=pred,
                occurrences=len(times),
                seconds=math.fsum(times),
                share_of_error_time=math.fsum(times) / error_time,
            )
            for (ref, pred), times in by_pair.items()
        ],
        key=lambda item: (-item["seconds"], item["reference"], item["prediction"]),
    )
    chords = []
    for item in diagnostics["per_chord"]:
        precision = ratio(item["correct_seconds"], item["predicted_seconds"])
        recall = item["recall"]
        f1 = (
            ratio(2 * precision * recall, precision + recall) or 0.0
            if precision is not None and recall is not None
            else None
        )
        chords.append(dict(**item, precision=precision, f1=f1))
    bins = []
    for index in range(BIN_COUNT):
        start, end = duration * (index / BIN_COUNT), duration * ((index + 1) / BIN_COUNT)
        categories = {
            name: math.fsum(
                overlap(start, end, r["start"], r["end"])
                for r in diagnostics["error_regions"]
                if r["category"] == name
            )
            for name in diagnostics["error_seconds"]
        }
        errors = math.fsum(categories.values())
        bins.append(
            dict(
                start=start,
                end=end,
                error_seconds=errors,
                error_fraction=ratio(errors, end - start),
                categories=categories,
            )
        )
    changes = []
    previous = None
    for segment in result["reference"].segments:
        label = canonical_label(segment.label)
        if previous is not None and label != previous:
            changes.append(segment.start)
        previous = label
    windows = []
    for boundary in changes:
        left, right = max(0, boundary - BOUNDARY_RADIUS), min(duration, boundary + BOUNDARY_RADIUS)
        if windows and left <= windows[-1][1]:
            windows[-1][1] = max(right, windows[-1][1])
        else:
            windows.append([left, right])
    near_time = math.fsum(right - left for left, right in windows)
    near_error = math.fsum(
        overlap(region["start"], region["end"], left, right)
        for region in diagnostics["error_regions"]
        for left, right in windows
    )
    away_time = max(0, duration - near_time)
    away_error = max(0, error_time - near_error)
    boundary = dict(
        radius_seconds=BOUNDARY_RADIUS,
        reference_change_count=len(changes),
        windows=windows,
        near=dict(
            seconds=near_time, error_seconds=near_error, error_fraction=ratio(near_error, near_time)
        ),
        away=dict(
            seconds=away_time, error_seconds=away_error, error_fraction=ratio(away_error, away_time)
        ),
        interpretation="proximity to reference changes; does not establish latency or error cause",
    )
    chord_segments = [s for s in segments if s["reference"] != "N"]
    chord_time = math.fsum(s["end"] - s["start"] for s in chord_segments)
    n_time = math.fsum(s["end"] - s["start"] for s in segments if s["reference"] == "N")
    slices = dict(
        reference_chord_seconds=chord_time,
        chord_only={
            name: ratio(
                math.fsum((s["end"] - s["start"]) * s[field] for s in chord_segments), chord_time
            )
            for name, field in (("root", "root_match"), ("major_minor", "major_minor_match"))
        },
        reference_n_seconds=n_time,
        n_recall=ratio(
            math.fsum(
                s["end"] - s["start"] for s in segments if s["reference"] == s["prediction"] == "N"
            ),
            n_time,
        ),
    )
    findings = [
        f"Chord labels disagree for {error_time:.3f} s "
        f"({100 * error_time / duration:.2f}% of evaluated time)."
    ]
    if patterns:
        top = patterns[0]
        findings.append(
            f"Largest confusion: {top['reference']} -> {top['prediction']}, "
            f"{top['seconds']:.3f} s; separate regions: {top['occurrences']}."
        )
        worst = max(
            bins, key=lambda b: b["error_fraction"] if b["error_fraction"] is not None else -1
        )
        findings.append(
            f"Highest disagreement among ten equal-duration windows: "
            f"{worst['start']:.3f}-{worst['end']:.3f} s ({100 * worst['error_fraction']:.2f}%)."
        )
    if near_time and away_time:
        findings.append(
            f"Disagreement occupies {100 * near_error / near_time:.2f}% of time within "
            f"+/-{BOUNDARY_RADIUS} s of reference changes "
            f"and {100 * away_error / away_time:.2f}% elsewhere."
        )
    return dict(
        method="duration-based descriptive analysis v1; no causal or significance claims",
        error_summary=summary,
        error_episodes=episodes,
        confusion_patterns=patterns,
        root_offsets=[
            dict(semitones_modulo_12=k, seconds=math.fsum(v)) for k, v in sorted(offsets.items())
        ],
        per_chord=chords,
        temporal_bins=bins,
        boundary_proximity=boundary,
        reference_slices=slices,
        findings=findings,
    )
