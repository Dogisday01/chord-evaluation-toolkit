"""Expected numbers come from hand-counted time, not this implementation."""

import hashlib
import json
import random
import subprocess
import sys

import pytest

from chord_eval.cli import main
from chord_eval.evaluation import score_annotations
from chord_eval.io import load_annotation
from chord_eval.models import AnnotationError
from chord_eval.reporting import build_report, write_report


def pair(tmp_path, ref, pred):
    paths = (tmp_path / "ref.lab", tmp_path / "pred.lab")
    for path, content in zip(paths, (ref, pred)):
        path.write_text(content, encoding="utf-8")
    return tuple(load_annotation(path) for path in paths)


@pytest.mark.parametrize(
    "ref,pred,expected",
    [
        ("0 10 C:maj", "0 10 C:maj", (1, 1)),
        ("0 8 C:maj\n8 10 G:maj", "0 8 C:maj\n8 10 A:min", (0.8, 0.8)),
        ("0 4 C:maj\n4 10 G:maj", "0 5 C:maj\n5 10 G:maj", (0.9, 0.9)),
        ("0 10 C:maj", "0 10 C:min", (1, 0)),
        ("0 10 C:maj", "0 10 G:maj", (0, 0)),
        ("0 10 N", "0 10 N", (1, 1)),
        ("0 10 N", "0 10 C:maj", (0, 0)),
        ("0 10 C:maj", "0 10 N", (0, 0)),
        ("0 10 C#:min", "0 10 Db:min", (1, 1)),
        ("0 10 Cb:maj", "0 10 B:maj", (1, 1)),
    ],
)
def test_known_answers(tmp_path, ref, pred, expected):
    scores = score_annotations(*pair(tmp_path, ref, pred))["metrics"]
    assert (scores["root"], scores["major_minor"]) == pytest.approx(expected)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "  \n",
        "-1 10 C:maj",
        "0 0 C:maj",
        "1 0 C:maj",
        "1 10 C:maj",
        "0 nan C:maj",
        "0 inf C:maj",
        "nan 10 C:maj",
        "0 1e999 C:maj",
        "0 5 C:maj\n4 10 G:maj",
        "0 4 C:maj\n5 10 G:maj",
        "0 4 C:maj\n5 6 G:maj\n4 10 C:maj",
        "0 10 Q:maj",
        "0 10 C:dim",
        "0 10 C:7",
        "0 10 C",
        "0 10 C:maj/3",
        "0 10 X",
        "0 10",
        "0 10 C:maj extra",
        "zero 10 C:maj",
        "0 1 C:maj\n0.9999999995 0.9999999998 G:maj",
    ],
)
def test_reject_invalid_inputs(tmp_path, content):
    path = tmp_path / "bad.lab"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AnnotationError, match="bad.lab"):
        load_annotation(path)


def test_incompatible_coverage(tmp_path):
    with pytest.raises(AnnotationError, match="same"):
        score_annotations(*pair(tmp_path, "0 10 C:maj", "0 11 C:maj"))


def test_bom_and_snapshot_digest(tmp_path):
    path = tmp_path / "input.lab"
    raw = b"\xef\xbb\xbf0 10 C:maj\r\n"
    path.write_bytes(raw)
    annotation = load_annotation(path)
    assert annotation.sha256 == hashlib.sha256(raw).hexdigest()
    path.write_text("0 10 G:maj", encoding="utf-8")
    assert annotation.segments[0].label == "C:maj"


def test_bad_encoding(tmp_path):
    path = tmp_path / "bad.lab"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(AnnotationError, match="UTF-8"):
        load_annotation(path)


def test_rounding_is_recorded(tmp_path):
    result = score_annotations(
        *pair(tmp_path, "0 4 C:maj\n4 10 G:maj", "0 4 C:maj\n4.0000000005 10.0000000005 G:maj")
    )
    report = build_report(result)
    assert report["metrics"]["major_minor"] == 1
    changes = report["inputs"]["prediction"]["boundary_adjustments"]
    assert len(changes) == 2
    assert {change["field"] for change in changes} == {"start", "end"}


@pytest.mark.parametrize("scale", [0.001, 1, 1000])
def test_time_scaling_and_interval_splitting(tmp_path, scale):
    result = score_annotations(
        *pair(
            tmp_path,
            f"0 {2 * scale} C:maj\n{2 * scale} {8 * scale} C:maj\n{8 * scale} {10 * scale} G:maj",
            f"0 {8 * scale} C:maj\n{8 * scale} {10 * scale} A:min",
        )
    )
    assert result["metrics"]["major_minor"] == pytest.approx(0.8)


def test_random_grids_against_independent_integer_time_oracle(tmp_path):
    # Integer-second samples provide a separate oracle. Boundaries are integer
    # seconds, so every half-second sample represents exactly one second.
    rng = random.Random(7421)
    vocabulary = [
        ("C:maj", "C", "maj"),
        ("C:min", "C", "min"),
        ("G:maj", "G", "maj"),
        ("N", None, None),
    ]
    for _ in range(30):
        texts, per_second = [], []
        for _role in range(2):
            boundaries = [0] + sorted(rng.sample(range(1, 20), 5)) + [20]
            rows, seconds = [], []
            for start, end in zip(boundaries[:-1], boundaries[1:]):
                label, root, quality = rng.choice(vocabulary)
                rows.append(f"{start} {end} {label}")
                seconds.extend([(root, quality)] * (end - start))
            texts.append("\n".join(rows))
            per_second.append(seconds)
        expected_root = sum(a[0] == b[0] for a, b in zip(*per_second)) / 20
        expected_quality = sum(a == b for a, b in zip(*per_second)) / 20
        scores = score_annotations(*pair(tmp_path, *texts))["metrics"]
        assert scores["root"] == pytest.approx(expected_root)
        assert scores["major_minor"] == pytest.approx(expected_quality)


def test_report_serialization_and_no_overwrite(tmp_path):
    report = build_report(score_annotations(*pair(tmp_path, "0 10 N", "0 10 N")), "test-rev")
    path = tmp_path / "result.json"
    write_report(report, path)
    assert json.loads(path.read_text())["tool"]["code_revision"] == "test-rev"
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_report({"other": "value"}, path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".chord-eval-*"))


def test_failed_publication_has_no_partial_output(tmp_path, monkeypatch):
    def fail_link(*args):
        raise OSError("unsupported filesystem")

    monkeypatch.setattr("chord_eval.reporting.os.link", fail_link)
    path = tmp_path / "result.json"
    with pytest.raises(OSError):
        write_report({"valid": True}, path)
    assert not path.exists()
    assert not list(tmp_path.glob(".chord-eval-*"))


def test_invalid_json_never_publishes(tmp_path):
    path = tmp_path / "result.json"
    with pytest.raises(ValueError):
        write_report({"invalid": float("nan")}, path)
    assert not path.exists()


def test_cli_success_and_errors(tmp_path, capsys):
    pair(tmp_path, "0 8 C:maj\n8 10 G:maj", "0 8 C:maj\n8 10 A:min")
    args = [str(tmp_path / "ref.lab"), str(tmp_path / "pred.lab")]
    assert main(["validate", *args]) == 0
    output = tmp_path / "result.json"
    assert main(["evaluate", *args, "--output", str(output)]) == 0
    assert "0.800000" in capsys.readouterr().out
    assert main(["evaluate", *args, "--output", str(output)]) == 3
    assert main(["validate", str(tmp_path / "missing"), args[1]]) == 3
    (tmp_path / "ref.lab").write_text("0 10 C:dim")
    assert main(["evaluate", *args, "--output", str(tmp_path / "bad.json")]) == 2
    assert not (tmp_path / "bad.json").exists()


def test_cli_process_exit_code(tmp_path):
    pair(tmp_path, "0 4 C:maj\n5 10 G:maj", "0 10 C:maj") if False else None
    invalid = tmp_path / "gap.lab"
    invalid.write_text("0 4 C:maj\n5 10 G:maj")
    prediction = tmp_path / "pred.lab"
    prediction.write_text("0 10 C:maj")
    process = subprocess.run(
        [sys.executable, "-m", "chord_eval.cli", "validate", str(invalid), str(prediction)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 2
    assert "gap.lab: line 2: gap" in process.stderr
