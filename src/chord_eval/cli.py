"""User operations: validate two files or evaluate and export their scores."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .api import evaluate_files
from .collection import run_experiment
from .evaluation import align_pair
from .html_report import render_html
from .io import load_annotation
from .models import AnnotationError
from .reporting import write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and score musical chord intervals")
    parser.add_argument("--version", action="version", version=f"chord-eval {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "evaluate", "batch", "compare"):
        sub = commands.add_parser(command)
        if command in ("validate", "evaluate"):
            sub.add_argument("reference")
            sub.add_argument("prediction")
        else:
            sub.add_argument("manifest")
        if command != "validate":
            sub.add_argument("--output", required=True)
            sub.add_argument("--html", help="optional offline interactive report")
            sub.add_argument(
                "--code-revision", help="Git commit or release identifier for provenance"
            )
        if command == "compare":
            sub.add_argument("--baseline", required=True)
            sub.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            ref, pred = align_pair(
                load_annotation(args.reference), load_annotation(args.prediction)
            )
            count = len(ref.adjustments) + len(pred.adjustments)
            print(f"Valid pair: {ref.duration:g} seconds; {count} boundary adjustment(s)")
            return 0
        if args.command == "evaluate":
            report = evaluate_files(
                args.reference, args.prediction, code_revision=args.code_revision
            )
        else:
            report = run_experiment(
                args.manifest,
                baseline=getattr(args, "baseline", None),
                candidate=getattr(args, "candidate", None),
                code_revision=args.code_revision,
            )
        outputs = {
            Path(args.output): (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
        }
        if args.html:
            if Path(args.output).resolve() == Path(args.html).resolve():
                raise OSError("JSON and HTML outputs must be different paths")
            outputs[Path(args.html)] = render_html(report).encode("utf-8")
        write_outputs(outputs)
        if report["kind"] == "pair":
            print(
                f"root={report['metrics']['root']:.6f}; "
                f"major_minor={report['metrics']['major_minor']:.6f}; report={args.output}"
            )
        else:
            print(
                f"Collection {report['status']}: {len(report['records'])} tracks; "
                f"report={args.output}"
            )
        return 2 if report.get("status") == "incomplete" else 0
    except AnnotationError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
