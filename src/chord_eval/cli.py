"""User operations: validate two files or evaluate and export their scores."""

import argparse
import sys

from . import __version__
from .evaluation import align_pair, score_annotations
from .io import load_annotation
from .models import AnnotationError
from .reporting import build_report, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and score musical chord intervals")
    parser.add_argument("--version", action="version", version=f"chord-eval {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "evaluate"):
        sub = commands.add_parser(command)
        sub.add_argument("reference")
        sub.add_argument("prediction")
        if command == "evaluate":
            sub.add_argument("--output", required=True)
            sub.add_argument(
                "--code-revision", help="Git commit or release identifier for provenance"
            )
    args = parser.parse_args(argv)
    try:
        ref, pred = align_pair(load_annotation(args.reference), load_annotation(args.prediction))
        if args.command == "validate":
            count = len(ref.adjustments) + len(pred.adjustments)
            print(f"Valid pair: {ref.duration:g} seconds; {count} boundary adjustment(s)")
            return 0
        result = score_annotations(ref, pred)
        write_report(build_report(result, args.code_revision), args.output)
        print(
            f"root={result['metrics']['root']:.6f}; "
            f"major_minor={result['metrics']['major_minor']:.6f}; report={args.output}"
        )
        return 0
    except AnnotationError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
