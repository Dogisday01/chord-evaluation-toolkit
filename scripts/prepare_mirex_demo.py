"""Fetch a pinned, score-independent real-data demonstration; keep every audit."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from chord_eval.api import annotation_from_intervals
from chord_eval.models import AnnotationError
from chord_eval.preparation import crop_rows, project_harte_label
from chord_eval.protocol import PROTOCOL_ID

SOURCE_REVISION = "be7f0e929d3452697f07a227cf1b533426eb2022"
BASE = (
    f"https://raw.githubusercontent.com/ismir-mirex/ace-output/{SOURCE_REVISION}/2018/Billboard2012"
)
MODELS = ("Ground-Truth", "FK2", "JLCX1")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ChordEvaluationToolkit/1.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def prepare_snapshot(raw, name):
    rows, mapping = [], {}
    try:
        lines = raw.decode("utf-8-sig").splitlines()
        for line in lines:
            if not line.strip():
                continue
            start, end, label = line.split()
            projected = project_harte_label(label)
            mapping[label] = projected
            rows.append((float(start), float(end), projected))
    except (UnicodeError, ValueError) as exc:
        raise AnnotationError(f"{name}: invalid three-column lab text") from exc
    annotation = annotation_from_intervals(rows, name)
    normalized = [(s.start, s.end, s.label) for s in annotation.segments]
    return normalized, dict(sorted(mapping.items())), list(annotation.adjustments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default="examples/real_mirex")
    args = parser.parse_args()
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=False)
    listing = json.loads(
        fetch(
            f"https://api.github.com/repos/ismir-mirex/ace-output/contents/2018/Billboard2012/Ground-Truth?ref={SOURCE_REVISION}"
        )
    )
    selection, tracks, imported = [], [], []
    for name in sorted(item["name"] for item in listing if item["name"].endswith(".lab")):
        snapshots, sources, reasons = {}, {}, []
        for model in MODELS:
            raw = fetch(f"{BASE}/{model}/{name}")
            raw_path = destination / "original" / model / name
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(raw)
            sources[model] = dict(
                url=f"{BASE}/{model}/{name}", sha256=hashlib.sha256(raw).hexdigest()
            )
            try:
                rows, mapping, adjustments = prepare_snapshot(raw, f"{model}/{name}")
                snapshots[model] = rows
                sources[model].update(
                    original_end_seconds=rows[-1][1],
                    label_projection=mapping,
                    rounding_adjustments=adjustments,
                )
            except AnnotationError as exc:
                reasons.append(f"{model}: {exc}")
        if not reasons:
            shared_end = min(rows[-1][1] for rows in snapshots.values())
            if any(rows[-1][1] - shared_end > 0.1 for rows in snapshots.values()):
                reasons.append(
                    "source endpoints differ by more than the declared 0.1-second preparation limit"
                )
        selection.append(dict(id=name[:-4], included=not reasons, reasons=reasons, sources=sources))
        if reasons:
            continue
        paths = {}
        for model, rows in snapshots.items():
            prepared = crop_rows(rows, shared_end)
            path = destination / "prepared" / model / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "".join(f"{s:.17g} {e:.17g} {label}\n" for s, e, label in prepared),
                encoding="utf-8",
            )
            paths[model] = path.relative_to(destination).as_posix()
            sources[model].update(
                evaluated_end_seconds=shared_end,
                removed_tail_seconds=rows[-1][1] - shared_end,
                prepared_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        tracks.append(
            dict(
                id=name[:-4],
                reference=paths["Ground-Truth"],
                predictions={m: paths[m] for m in MODELS[1:]},
            )
        )
        imported.append(dict(id=name[:-4], evaluated_end_seconds=shared_end, sources=sources))
        if len(tracks) == 3:
            break
    if len(tracks) != 3:
        raise RuntimeError("three eligible records were not found; no evaluation manifest created")
    audit = dict(
        source_revision=SOURCE_REVISION,
        selection_rule=(
            "first three filenames in lexical order with fully projectable labels, "
            "strict continuous input and endpoint spread <=0.1 s; no scores used"
        ),
        preparation_rule=(
            "Harte pitch set must contain exactly one complete major/minor triad; "
            "discard additional tones and bass; canonical roots; common "
            "[0,min(end)] coverage; no padding, shifts or internal exclusions"
        ),
        interpretation=(
            "real published annotations and algorithm outputs on selected prepared "
            "excerpts; not our trained models, a representative corpus benchmark "
            "or official MIREX scores"
        ),
        scanned=selection,
        imported=imported,
    )
    (destination / "preparation_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    manifest = dict(
        schema_version="1.0",
        dataset_id="mirex2018_billboard2012_three_record_demo",
        split="test",
        protocol_id=PROTOCOL_ID,
        data_provenance=dict(
            source="https://github.com/ismir-mirex/ace-output/tree/master/2018/Billboard2012",
            source_revision=SOURCE_REVISION,
            preparation=audit["preparation_rule"],
            selection=audit["selection_rule"],
            audit_file="preparation_audit.json",
        ),
        models={
            m: dict(
                description=(
                    f"Published MIREX 2018 {m} output; evaluated after declared "
                    "major/minor projection and common-coverage preparation"
                )
            )
            for m in MODELS[1:]
        },
        tracks=tracks,
    )
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                selected=[t["id"] for t in tracks],
                scanned=len(selection),
                manifest=str(destination / "manifest.json"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
