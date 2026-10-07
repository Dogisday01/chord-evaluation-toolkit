"""Install the built wheel outside the checkout and exercise its real entry point."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path


def run(command, cwd, env):
    return subprocess.run(command, cwd=cwd, env=env, check=True, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
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
        evidence = {
            "wheel": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "installed_outside_checkout": True,
            "pip_check": "passed",
            "example_metrics": report["metrics"],
            "invalid_gap_exit_code": 2,
            "environment": report["environment"],
        }
    destination = Path(args.evidence)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
