"""Install the built wheel outside the checkout and exercise its real entry point."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import venv
from pathlib import Path


def run(command, cwd, env):
    return subprocess.run(command, cwd=cwd, env=env, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    package_version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    wheels = list((root / "dist").glob(f"chord_evaluation_toolkit-{package_version}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("expected exactly one built wheel in dist")
    wheel = wheels[0]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="chord-eval-wheel-") as directory:
        working = Path(directory).resolve()
        environment = working / "isolated"
        venv.EnvBuilder(with_pip=True).create(environment)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("chord-eval.exe" if os.name == "nt" else "chord-eval")
        run([str(python), "-m", "pip", "install", str(wheel)], working, env)
        run([str(python), "-m", "pip", "check"], working, env)
        for name in ("reference.lab", "prediction.lab", "invalid_gap.lab"):
            shutil.copyfile(root / "examples" / name, working / name)
        run([str(cli), "validate", "reference.lab", "prediction.lab"], working, env)
        run(
            [str(cli), "evaluate", "reference.lab", "prediction.lab", "--output", "report.json"],
            working,
            env,
        )
        report = json.loads((working / "report.json").read_text())
        if any(abs(score - 0.8) > 1e-12 for score in report["metrics"].values()):
            raise RuntimeError("wheel example does not produce the hand-counted 8/10 score")
        location = run(
            [str(python), "-c", "import chord_eval; print(chord_eval.__file__)"], working, env
        ).stdout.strip()
        if not Path(location).resolve().is_relative_to(environment):
            raise RuntimeError("package was loaded from the checkout instead of the wheel")
        rejected = subprocess.run(
            [str(cli), "evaluate", "invalid_gap.lab", "prediction.lab", "--output", "bad.json"],
            cwd=working,
            env=env,
            capture_output=True,
            text=True,
        )
        if rejected.returncode != 2 or (working / "bad.json").exists():
            raise RuntimeError("wheel did not reject invalid data without publishing a report")
        shutil.copytree(root / "examples" / "collection", working / "collection")
        run(
            [
                str(cli),
                "compare",
                "collection/manifest.json",
                "--baseline",
                "baseline",
                "--candidate",
                "candidate",
                "--output",
                "comparison.json",
                "--html",
                "comparison.html",
            ],
            working,
            env,
        )
        comparison = json.loads((working / "comparison.json").read_text())
        a, b = comparison["summary"]["baseline"], comparison["summary"]["candidate"]
        if (
            abs(a["micro"]["major_minor"] - 0.75) > 1e-12
            or abs(b["micro"]["major_minor"] - 0.85) > 1e-12
        ):
            raise RuntimeError("installed wheel collection disagrees with hand-counted seconds")
        html = (working / "comparison.html").read_text(encoding="utf-8")
        if 'id="report-data"' not in html or "__REPORT_DATA__" in html:
            raise RuntimeError("installed wheel did not deliver its offline viewer resource")
        adapter = run(
            [
                str(python),
                "-c",
                "import json; from chord_eval.api import evaluate_intervals; "
                "r=evaluate_intervals([(0,10,'C:maj')],[(0,10,'C:min')]); "
                "print(json.dumps(r['metrics']))",
            ],
            working,
            env,
        )
        if json.loads(adapter.stdout) != {"root": 1.0, "major_minor": 0.0}:
            raise RuntimeError("installed public adapter violates the known-answer case")
        shutil.copytree(root / "examples" / "real_mirex", working / "real_mirex")
        run(
            [
                str(cli),
                "compare",
                "real_mirex/manifest.json",
                "--baseline",
                "FK2",
                "--candidate",
                "JLCX1",
                "--output",
                "real.json",
                "--html",
                "real.html",
            ],
            working,
            env,
        )
        real = json.loads((working / "real.json").read_text())
        expected = {"FK2": 0.9468402950967814, "JLCX1": 0.944928179956164}
        if real["status"] != "complete" or any(
            abs(real["summary"][model]["micro"]["major_minor"] - value) > 1e-12
            for model, value in expected.items()
        ):
            raise RuntimeError("installed wheel real-data example disagrees with verified oracle")
        if "analysis" not in real["records"][0]["evaluations"]["FK2"]:
            raise RuntimeError("installed wheel has no detailed analysis")
        evidence = {
            "wheel": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "installed_outside_checkout": True,
            "pip_check": "passed",
            "example_metrics": report["metrics"],
            "invalid_gap_exit_code": 2,
            "environment": report["environment"],
            "tool_version": report["tool"]["version"],
            "collection_micro": {"baseline": a["micro"], "candidate": b["micro"]},
            "collection_macro": {"baseline": a["macro"], "candidate": b["macro"]},
            "html_resource": "exported from installed wheel",
            "public_interval_api": "passed",
            "real_data_micro": {m: s["micro"] for m, s in real["summary"].items()},
            "real_data_track_count": len(real["records"]),
            "detailed_analysis": "passed",
        }
    destination = Path(args.evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
