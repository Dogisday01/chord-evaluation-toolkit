"""Known answers and independent oracles for descriptive analysis and real data."""

import hashlib
import json
import random
from pathlib import Path

import pytest

from chord_eval.api import evaluate_intervals
from chord_eval.collection import load_manifest, run_experiment
from chord_eval.models import AnnotationError
from chord_eval.preparation import crop_rows, project_harte_label

REAL = Path(__file__).resolve().parents[1] / "examples" / "real_mirex"


def test_known_episodes_patterns_and_precision():
    report = evaluate_intervals(
        [(0, 10, "C:maj")],
        [(0, 2, "C:maj"), (2, 4, "G:maj"), (4, 6, "C:min"), (6, 8, "C:maj"), (8, 10, "G:maj")],
    )
    a = report["analysis"]
    assert a["error_summary"]["error_seconds"] == 6
    assert a["error_summary"]["episode_count"] == 2
    assert a["error_summary"]["mean_episode_seconds"] == 3
    assert a["error_summary"]["longest_episode"] == dict(start=2, end=6, duration_seconds=4)
    assert a["confusion_patterns"][0] == dict(
        reference="C:maj", prediction="G:maj", occurrences=2, seconds=4, share_of_error_time=2 / 3
    )
    c, g = (
        {i["label"]: i for i in a["per_chord"]}["C:maj"],
        {i["label"]: i for i in a["per_chord"]}["G:maj"],
    )
    assert c["precision"] == 1 and c["recall"] == 0.4
    assert c["f1"] == pytest.approx(4 / 7)
    assert g["precision"] == 0 and g["recall"] is None and g["f1"] is None
    assert a["root_offsets"] == [dict(semitones_modulo_12=7, seconds=4)]
    assert [b["error_fraction"] for b in a["temporal_bins"]] == [0, 0, 1, 1, 1, 1, 0, 0, 1, 1]


def test_boundary_proximity_counts_time_without_claiming_latency():
    a = evaluate_intervals(
        [(0, 5, "C:maj"), (5, 10, "G:maj")], [(0, 5.2, "C:maj"), (5.2, 10, "G:maj")]
    )["analysis"]
    b = a["boundary_proximity"]
    assert b["windows"] == [[4.75, 5.25]]
    assert b["near"]["seconds"] == 0.5
    assert b["near"]["error_seconds"] == pytest.approx(0.2)
    assert b["near"]["error_fraction"] == pytest.approx(0.4)
    assert b["away"] == dict(seconds=9.5, error_seconds=0, error_fraction=0)


def test_overlapping_boundary_windows_are_counted_once():
    a = evaluate_intervals(
        [(0, 0.1, "C:maj"), (0.1, 0.2, "G:maj"), (0.2, 1, "C:maj")], [(0, 1, "N")]
    )["analysis"]
    b = a["boundary_proximity"]
    assert len(b["windows"]) == 1
    assert b["near"]["seconds"] == pytest.approx(0.45)
    assert b["near"]["error_seconds"] == pytest.approx(0.45)
    assert b["near"]["error_fraction"] == 1
    assert b["away"]["error_fraction"] == 1


def test_empty_support_and_perfect_labels_have_honest_nulls():
    a = evaluate_intervals([(0, 10, "N")], [(0, 10, "N")])["analysis"]
    assert a["reference_slices"]["chord_only"] == dict(root=None, major_minor=None)
    assert a["reference_slices"]["n_recall"] == 1
    assert a["error_summary"]["mean_episode_seconds"] is None
    assert a["error_summary"]["longest_episode"] is None
    assert a["boundary_proximity"]["near"]["error_fraction"] is None
    assert a["confusion_patterns"] == []
    assert len(a["findings"]) == 1
    chord = evaluate_intervals([(0, 10, "C:maj")], [(0, 10, "C:maj")])["analysis"]
    assert chord["reference_slices"]["n_recall"] is None
    for duration in (1e308, 5e-324):
        extremes = evaluate_intervals([(0, duration, "C:maj")], [(0, duration, "C:maj")])
        json.dumps(extremes, allow_nan=False)
        assert all(b["error_fraction"] in (0, None) for b in extremes["analysis"]["temporal_bins"])


def test_row_splitting_and_enharmonics_do_not_change_analysis():
    reference = [(0, 5, "C#:maj"), (5, 10, "G:maj")]
    a = evaluate_intervals(reference, [(0, 10, "G:maj")])["analysis"]
    b = evaluate_intervals(
        [(0, 2, "Db:maj"), (2, 5, "C#:maj"), (5, 10, "G:maj")], [(0, 3, "G:maj"), (3, 10, "G:maj")]
    )["analysis"]
    assert a == b


def test_integer_step_oracle_on_random_examples():
    rng = random.Random(718)
    alphabet = ("C:maj", "G:maj", "C:min", "N")
    for _ in range(30):
        ref = [rng.choice(alphabet) for _ in range(20)]
        pred = [rng.choice(alphabet) for _ in range(20)]

        def rows(labels):
            return [(i, i + 1, label) for i, label in enumerate(labels)]

        a = evaluate_intervals(rows(ref), rows(pred))["analysis"]
        assert a["error_summary"]["error_seconds"] == sum(x != y for x, y in zip(ref, pred))
        assert [b["error_seconds"] for b in a["temporal_bins"]] == [
            sum(ref[j] != pred[j] for j in range(i, i + 2)) for i in range(0, 20, 2)
        ]
        assert (
            sum(b["error_seconds"] for b in a["temporal_bins"])
            == a["error_summary"]["error_seconds"]
        )
        for item in a["per_chord"]:
            label = item["label"]
            correct = sum(x == y == label for x, y in zip(ref, pred))
            expected_p = correct / pred.count(label) if label in pred else None
            expected_r = correct / ref.count(label) if label in ref else None
            assert item["precision"] == expected_p
            assert item["recall"] == expected_r


@pytest.mark.parametrize(
    "source,expected",
    [
        ("C", "C:maj"),
        ("Db:7/3", "C#:maj"),
        ("A:min7", "A:min"),
        ("F:maj9", "F:maj"),
        ("G:min6", "G:min"),
        ("N", "N"),
    ],
)
def test_declared_harte_projection(source, expected):
    assert project_harte_label(source) == expected


@pytest.mark.parametrize("source", ["X", "C:dim", "C:aug", "C:sus4", "C:1/1", "C:maj(*3)"])
def test_unknown_and_nontriadic_chords_are_never_silence(source):
    with pytest.raises(AnnotationError):
        project_harte_label(source)


def test_explicit_excerpt_does_not_pad_or_move_time():
    rows = [(0, 3, "C:maj"), (3, 10, "G:maj")]
    assert crop_rows(rows, 8) == [(0, 3, "C:maj"), (3, 8, "G:maj")]
    assert crop_rows(rows, 3) == [(0, 3, "C:maj")]
    with pytest.raises(AnnotationError):
        crop_rows(rows, 11)


def test_real_demo_source_hashes_selection_and_recorded_preparation():
    audit = json.loads((REAL / "preparation_audit.json").read_text())
    assert [r["id"] for r in audit["imported"]] == ["1006", "1007", "1011"]
    assert [r["id"] for r in audit["scanned"] if not r["included"]] == ["1002", "1003", "1009"]
    for item in audit["scanned"]:
        for model, source in item["sources"].items():
            raw = (REAL / "original" / model / (item["id"] + ".lab")).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    for item in audit["imported"]:
        for model, source in item["sources"].items():
            prepared = (REAL / "prepared" / model / (item["id"] + ".lab")).read_bytes()
            assert hashlib.sha256(prepared).hexdigest() == source["prepared_sha256"]
            assert 0 <= source["removed_tail_seconds"] <= 0.1
            assert (
                source["original_end_seconds"] - source["removed_tail_seconds"]
                == item["evaluated_end_seconds"]
            )


def test_real_demo_independent_exact_interval_oracle():
    manifest, _ = load_manifest(REAL / "manifest.json")
    report = run_experiment(REAL / "manifest.json", baseline="FK2", candidate="JLCX1")
    assert report["status"] == "complete"

    def read(path):
        return [
            (float(s), float(e), label)
            for s, e, label in (line.split() for line in (REAL / path).read_text().splitlines())
        ]

    for track, record in zip(manifest["tracks"], report["records"]):
        ref = read(track["reference"])
        for model, path in track["predictions"].items():
            pred = read(path)
            boundaries = sorted({t for s, e, _ in ref + pred for t in (s, e)})
            correct = dict(root=0.0, major_minor=0.0)
            for left, right in zip(boundaries, boundaries[1:]):
                t = (left + right) / 2
                a = next(label for s, e, label in ref if s <= t < e)
                b = next(label for s, e, label in pred if s <= t < e)
                correct["major_minor"] += (right - left) * (a == b)
                correct["root"] += (right - left) * (a.split(":")[0] == b.split(":")[0])
            result = record["evaluations"][model]
            for metric, time in correct.items():
                assert result["metrics"][metric] == pytest.approx(time / ref[-1][1], abs=1e-12)
            assert sum(
                i["error_seconds"] for i in result["analysis"]["temporal_bins"]
            ) == pytest.approx(result["duration_seconds"] - correct["major_minor"], abs=1e-10)


def test_collection_patterns_count_affected_recordings_once():
    r = run_experiment(REAL / "manifest.json")
    for model, summary in r["summary"].items():
        for pattern in summary["analysis"]["confusion_patterns"]:
            matches = [
                p
                for record in r["records"]
                for p in record["evaluations"][model]["analysis"]["confusion_patterns"]
                if (p["reference"], p["prediction"])
                == (pattern["reference"], pattern["prediction"])
            ]
            assert pattern["recording_count"] == len(matches)
            assert pattern["seconds"] == pytest.approx(sum(p["seconds"] for p in matches))


def test_data_provenance_is_validated_and_preserved(tmp_path):
    manifest = json.loads((REAL / "manifest.json").read_text())
    manifest["data_provenance"]["preparation"] = 123
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(AnnotationError, match="all values must be strings"):
        load_manifest(path)
