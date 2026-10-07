# Chord Evaluation Toolkit

Evaluate musical chord interval predictions against a reference and export a traceable JSON report. This scientific module continues the Evaluation and Reporting/Export components of the chord recognition project assessed in Assignment 2.

It evaluates supplied annotations. It does not train a model, decode audio, or demonstrate recognition accuracy on a music dataset.

## Install and run

Python 3.11, 3.12 or 3.13 is required. From this repository root:

```text
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on Linux/macOS, then:

```text
python -m pip install .
chord-eval validate examples/reference.lab examples/prediction.lab
chord-eval evaluate examples/reference.lab examples/prediction.lab --output report.json
```

Expected synthetic example: `root=0.800000; major_minor=0.800000`. Eight seconds of ten match. This is a known-answer example, not a model benchmark. Choose a new output filename for each run. An existing output is never overwritten.

To identify the code used, pass `--code-revision COMMIT_OR_TAG`. Record `git rev-parse HEAD` when evaluating a development checkout. `chord-eval --version` reports the package version.

## User behavior

Select reference and prediction files → validate or evaluate → inspect scores and aligned intervals → save JSON. Invalid input produces an actionable error before scoring. These are operations of the finished tool; model training and repository management are development activities.

## Input contract

UTF-8 `.lab` text (UTF-8 BOM accepted), three whitespace-separated columns:

```text
0 8 C:maj
8 10 G:maj
```

Times are seconds; intervals are half-open `[start, end)`. Blank lines are ignored. Labels must be explicit `ROOT:maj`, `ROOT:min`, or `N`; root is A–G with an optional single `#` or `b`. Enharmonic equivalents are compared by mir_eval. Bare `C`, extensions, inversions and `X` are rejected by this deliberately restricted alphabet.

Both files must cover the same continuous `[0, T]`, with finite nonnegative times, positive durations, ordered intervals and no gaps or overlaps. Boundary discrepancies of at most `1e-9` seconds are snapped to the previous end; prediction's final end is snapped to reference's end within the same tolerance. Every adjustment is recorded in JSON and counted by `validate`. Larger discrepancies fail; files are not silently sorted, trimmed or padded.

The merged grid uses boundaries from both files. Root and major/minor correctness are weighted by duration. A root match with the wrong chord quality can have root=1 and major_minor=0. Unsupported comparison values fail explicitly instead of silently changing the denominator.

## Report and errors

JSON includes schema/tool versions, an optional code revision, input SHA-256 digests, dependency and Python versions, evaluation protocol, metrics, aligned segments, normalization records and UTC creation time. Hashes describe the exact bytes parsed. Filenames, rather than machine-specific absolute paths, make reports portable. The `run` timestamp is expected to differ between otherwise identical runs.

Exit codes: 0 success; 2 invalid annotation or command usage; 3 file reading/writing error. Output publication uses a complete staging file and a create-if-absent hard link on the destination filesystem. NTFS and standard Linux filesystems are supported; a filesystem without hard-link support fails explicitly. The parent directory must already exist. Failed publication leaves no partial final report.

## Development and CI/CD

```text
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m ruff check .
python -m pytest --junitxml=test-results.xml
python -m build --no-isolation
```

[CI/CD configuration](.github/workflows/ci.yml) runs lint, known-answer and failure tests on Windows and Linux, builds wheel/sdist, installs the wheel in an isolated environment and checks the documented example. It retains test results and distribution artifacts. Delivery means an installable artifact; no production web deployment is claimed. A tag identifies a release candidate, while tests must still pass.

[Architecture and traceability](docs/design.md) explain the implemented requirements. [Validation method](docs/validation.md) records independent expectations and scientific limits. [Contribution process](CONTRIBUTING.md) defines small tasks, branches and change review.

## License and data

The project is [MIT licensed](LICENSE). Example intervals are authored synthetic fixtures. No music recordings, restricted dataset files, trained checkpoints or credentials are included. Dependencies retain their own licenses. The module's correctness tests establish evaluation behavior, not the predictive quality of any model.
