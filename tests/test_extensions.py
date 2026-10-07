"""Counterexamples and fixed answers from extension_acceptance.md."""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from chord_eval.api import annotation_from_intervals, evaluate_files, evaluate_intervals
from chord_eval.cli import main
from chord_eval.collection import load_manifest, run_experiment
from chord_eval.html_report import render_html
from chord_eval.models import AnnotationError
from chord_eval.reporting import write_outputs

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "collection"


@pytest.mark.parametrize(
    "ref,pred,category",
    [
        ("C:maj", "C:min", "wrong_quality"),
        ("C:maj", "G:min", "wrong_root"),
        ("C:maj", "N", "missed_chord"),
        ("N", "C:maj", "false_chord"),
    ],
)
def test_error_category_and_seconds(ref, pred, category):
    report = evaluate_intervals([(0, 10, ref)], [(0, 4, pred), (4, 10, pred)])
    diagnostics = report["diagnostics"]
    assert diagnostics["error_seconds"][category] == 10
    assert sum(diagnostics["error_seconds"].values()) == 10
    assert len(diagnostics["error_regions"]) == 1
    assert diagnostics["error_regions"][0]["duration_seconds"] == 10
    assert sum(c["seconds"] for c in diagnostics["confusion_seconds"]) == 10


def test_enharmonics_and_duplicate_rows_do_not_create_errors_or_changes():
    report = evaluate_intervals(
        [(0, 10, "C#:maj")], [(0, 2, "Db:maj"), (2, 6, "C#:maj"), (6, 10, "Db:maj")]
    )
    d = report["diagnostics"]
    assert d["error_regions"] == []
    assert d["segmentation"] == {"overseg": 1, "underseg": 1, "seg": 1}
    assert d["per_chord"] == [
        dict(
            label="C#:maj", reference_seconds=10, predicted_seconds=10, correct_seconds=10, recall=1
        )
    ]


def test_actual_extra_change_has_known_segmentation_score():
    report = evaluate_intervals([(0, 10, "C:maj")], [(0, 5, "C:maj"), (5, 10, "G:maj")])
    assert report["diagnostics"]["segmentation"] == {"overseg": 0.5, "underseg": 1, "seg": 0.5}
    g = next(c for c in report["diagnostics"]["per_chord"] if c["label"] == "G:maj")
    assert g["recall"] is None  # Predicted but never present in the reference.


def test_perfect_segmentation_does_not_imply_correct_chord_names():
    report = evaluate_intervals(
        [(0, 5, "C:maj"), (5, 10, "G:maj")], [(0, 5, "D:min"), (5, 10, "A:min")]
    )
    assert report["metrics"] == {"root": 0, "major_minor": 0}
    assert report["diagnostics"]["segmentation"] == {"overseg": 1, "underseg": 1, "seg": 1}


def test_longest_errors_rank_duration_and_keep_correct_breaks():
    report = evaluate_intervals(
        [(0, 10, "C:maj")], [(0, 2, "G:maj"), (2, 3, "C:maj"), (3, 10, "G:maj")]
    )
    d = report["diagnostics"]
    assert len(d["error_regions"]) == 2
    assert [r["duration_seconds"] for r in d["longest_errors"]] == [7, 2]
    assert d["error_seconds"]["wrong_root"] == 9


def test_adapter_and_file_scores_match_and_hash_kinds_are_honest(tmp_path):
    rows = [(np.float32(0), np.float64(8), "C:maj"), (8, 10, "G:maj")]
    report = evaluate_intervals(rows, [(0, 10, "C:maj")])
    ref, pred = tmp_path / "ref.lab", tmp_path / "pred.lab"
    ref.write_text("0 8 C:maj\n8 10 G:maj", encoding="utf-8")
    pred.write_text("0 10 C:maj", encoding="utf-8")
    file_report = evaluate_files(ref, pred)
    assert report["metrics"] == file_report["metrics"]
    assert report["diagnostics"] == file_report["diagnostics"]
    assert report["inputs"]["reference"]["hash_representation"] == "canonical_interval_json_v1"
    expected = hashlib.sha256(b'[[0.0,8.0,"C:maj"],[8.0,10.0,"G:maj"]]').hexdigest()
    assert report["inputs"]["reference"]["sha256"] == expected
    assert file_report["inputs"]["reference"]["hash_representation"] == "original_utf8_lab_bytes"


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [],
        [(True, 10, "C:maj")],
        [("0", 10, "C:maj")],
        [(0, 10, None)],
        [(0, float("inf"), "C:maj")],
        [(0, 10, "C:7")],
        [(0, 5, "C:maj"), (6, 10, "G:maj")],
        [(0, 10)],
        [(0, 10, "C:maj", "extra")],
    ],
)
def test_adapter_cannot_bypass_input_contract(rows):
    with pytest.raises(AnnotationError):
        annotation_from_intervals(rows)


def test_collection_hand_counted_macro_micro_and_paired_deltas():
    result = run_experiment(EXAMPLES / "manifest.json", baseline="baseline", candidate="candidate")
    assert result["status"] == "complete"
    a, b = result["summary"]["baseline"], result["summary"]["candidate"]
    assert a["duration_seconds"] == 20
    assert a["micro"] == pytest.approx(dict(root=0.85, major_minor=0.75))
    assert a["macro"] == pytest.approx(dict(root=79 / 90, major_minor=32 / 45))
    assert b["micro"] == pytest.approx(dict(root=0.85, major_minor=0.85))
    assert b["macro"] == pytest.approx(dict(root=7 / 9, major_minor=7 / 9))
    comparison = result["comparison"]
    assert comparison["aggregate_delta"]["micro"] == pytest.approx(dict(root=0, major_minor=0.1))
    assert comparison["aggregate_delta"]["macro"]["major_minor"] == pytest.approx(1 / 15)
    assert comparison["outcomes"]["major_minor"] == dict(improved=1, worsened=0, tied=2)
    assert comparison["outcomes"]["root"] == dict(improved=1, worsened=1, tied=1)
    for record in result["records"]:
        inputs = [r["inputs"]["reference"]["sha256"] for r in record["evaluations"].values()]
        assert len(set(inputs)) == 1


def copy_collection(tmp_path):
    folder = tmp_path / "collection"
    shutil.copytree(EXAMPLES, folder)
    return folder / "manifest.json"


def test_invalid_record_cannot_improve_aggregate_by_being_dropped(tmp_path):
    manifest = copy_collection(tmp_path)
    (manifest.parent / "long_candidate.lab").write_text("0 4 C:maj\n5 10 G:maj")
    result = run_experiment(manifest, baseline="baseline", candidate="candidate")
    assert result["status"] == "incomplete"
    assert result["summary"] is None and result["comparison"] is None
    assert len(result["records"]) == 3
    assert result["records"][0]["errors"][0]["model"] == "candidate"
    assert "gap" in result["records"][0]["errors"][0]["message"]
    assert result["records"][1]["status"] == "valid"
    output, html = tmp_path / "report.json", tmp_path / "report.html"
    assert main(["batch", str(manifest), "--output", str(output), "--html", str(html)]) == 2
    assert json.loads(output.read_text())["status"] == "incomplete"
    assert html.is_file()


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_track",
        "missing_prediction",
        "protocol",
        "split",
        "unknown",
        "bad_hash",
        "bool_seed",
        "empty_tracks",
    ],
)
def test_manifest_rejects_ambiguous_experiments(tmp_path, mutation):
    manifest = copy_collection(tmp_path)
    data = json.loads(manifest.read_text())
    if mutation == "duplicate_track":
        data["tracks"].append(data["tracks"][0])
    elif mutation == "missing_prediction":
        del data["tracks"][0]["predictions"]["candidate"]
    elif mutation == "protocol":
        data["protocol_id"] = "different_vocabulary"
    elif mutation == "split":
        data["split"] = "guess"
    elif mutation == "unknown":
        data["typo"] = 1
    elif mutation == "bad_hash":
        data["models"]["baseline"]["checkpoint_sha256"] = "not_a_hash"
    elif mutation == "bool_seed":
        data["models"]["baseline"]["seed"] = True
    else:
        data["tracks"] = []
    manifest.write_text(json.dumps(data))
    with pytest.raises(AnnotationError):
        load_manifest(manifest)


@pytest.mark.parametrize(
    "text",
    ['{"schema_version":"1.0","schema_version":"2.0"}', '{"value":NaN}', '{"value":Infinity}'],
)
def test_json_duplicates_and_nonfinite_values_are_not_accepted(tmp_path, text):
    path = tmp_path / "manifest.json"
    path.write_text(text)
    with pytest.raises(AnnotationError):
        load_manifest(path)


@pytest.mark.parametrize(
    "baseline,candidate", [("baseline", "baseline"), ("unknown", "candidate"), ("baseline", None)]
)
def test_comparison_requires_two_declared_models(baseline, candidate):
    with pytest.raises(AnnotationError):
        run_experiment(EXAMPLES / "manifest.json", baseline=baseline, candidate=candidate)


def test_output_bundle_rolls_back_only_new_files(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "existing.html"
    second.write_bytes(b"original evidence")
    with pytest.raises(FileExistsError):
        write_outputs({first: b"new", second: b"replacement"})
    assert not first.exists()
    assert second.read_bytes() == b"original evidence"
    assert not list(tmp_path.glob(".chord-eval-*"))


def test_html_data_is_safe_and_preserves_report_values():
    report = evaluate_intervals([(0, 10, "C:maj")], [(0, 10, "C:min")])
    malicious = '</script><img src=x onerror="alert(1)"> & <name>'
    report["inputs"]["reference"]["name"] = malicious
    html = render_html(report)
    data = html.split('<script id="report-data" type="application/json">')[1].split("</script>")[0]
    assert "<" not in data and "&" not in data
    assert json.loads(data) == report
    assert malicious not in html
    assert "textContent=" in html


def test_compare_cli_and_output_path_collision(tmp_path):
    output, html = tmp_path / "comparison.json", tmp_path / "comparison.html"
    args = [
        "compare",
        str(EXAMPLES / "manifest.json"),
        "--baseline",
        "baseline",
        "--candidate",
        "candidate",
        "--output",
        str(output),
    ]
    assert main([*args, "--html", str(html)]) == 0
    assert json.loads(output.read_text())["comparison"]["baseline"] == "baseline"
    new = tmp_path / "same"
    args[args.index("--output") + 1] = str(new)
    assert main([*args, "--html", str(new)]) == 3
    assert not new.exists()
