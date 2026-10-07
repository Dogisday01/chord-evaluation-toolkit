# Chord Evaluation Toolkit

Evaluate chord predictions, inspect disagreements and compare experiments across recordings. Version 1.1 continues the Evaluation and Reporting/Export components of the chord recognition project assessed in Assignment 2, with a shared protocol and a public adapter interface.

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
chord-eval evaluate examples/reference.lab examples/prediction.lab --output detailed.json --html detailed.html
```

Expected synthetic example: `root=0.800000; major_minor=0.800000`. Eight seconds of ten match. This is a known-answer example, not a model benchmark. Choose a new output filename for each run. An existing output is never overwritten.

To identify the code used, pass `--code-revision COMMIT_OR_TAG`. Record `git rev-parse HEAD` when evaluating a development checkout. `chord-eval --version` reports the package version.

## User behavior

Select reference/prediction files or a collection manifest → evaluate or compare → open the HTML report → select a recording/model/error interval → inspect and save results. The browser report works as a local file and needs no server, account or internet. Training and repository management remain development activities.

The report identifies wrong roots, wrong major/minor quality, missed chords and false chords. It lists error intervals, the longest disagreements, time spent on chord confusions and recall by reference chord. Segmentation scores describe excess/missing changes, with repeated equivalent labels merged first. Higher is better; correct segmentation does not imply correct chord names.

## Collections and model comparison

```text
chord-eval batch examples/collection/manifest.json --output collection.json --html collection.html
chord-eval compare examples/collection/manifest.json --baseline baseline --candidate candidate --output comparison.json --html comparison.html
```

The manifest declares a dataset ID, split, protocol, model IDs and recording IDs with a common reference and one prediction file per model. Paths are relative to the manifest directory, or absolute local paths. Optional model metadata records checkpoint/configuration hashes, seed and code revision supplied by the caller. See [the schema and evaluation rules](docs/protocol.md).

The authored three-record demo totals 20 seconds. Baseline micro root=0.85 and major_minor=0.75; candidate micro both=0.85. Baseline macro root=0.877778 and major_minor=0.711111; candidate macro both=0.777778. Macro gives every recording equal weight; micro gives every second equal weight. Candidate quality improves, while root performance on the short recording worsens. These predetermined values are correctness fixtures, not trained-model results.

Comparison reports candidate-minus-baseline deltas and per-record changes under the same references and protocol. It makes no significance claim or automatic universal-winner decision. If any declared input is invalid/unreadable, the report is incomplete: individual results/errors remain inspectable, but aggregate scores and comparisons are unavailable. CLI saves that diagnostic report and returns 2. Malformed manifests fail before producing outputs. Fix the data and use new output names.

## Future model integration

```python
from chord_eval.api import evaluate_intervals

report = evaluate_intervals(
    [(0, 8, "C:maj"), (8, 10, "G:maj")],
    [(0, 8, "C:maj"), (8, 10, "A:min")],
    code_revision="experiment-identifier",
)
```

`evaluate_files` and `run_experiment` are also public API functions. A future model adapter converts its frames and label mapping to validated interval triples. This preserves independence from the model family. The API uses the same input rules, with hashes of canonical structured input explicitly distinguished from original file-byte hashes. The future audio/training modules still provide the checkpoint, split, seed and configuration records described in Assignment 2.

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

JSON schema 1.1 includes the report kind, tool version, optional code revision, SHA-256 digests, dependency/Python versions, protocol ID, metrics, diagnostics, aligned segments, normalization records and UTC creation time. File hashes describe the exact bytes parsed; in-memory hashes identify their documented canonical JSON representation. Collection reports retain the manifest hash and each pair's provenance. Filenames, rather than absolute paths, keep output portable. Run timestamps naturally differ between repeated executions.

Exit codes: 0 success; 2 invalid annotation/manifest, incomplete collection or command usage; 3 direct file reading/writing error. Output publication uses complete staging files and create-if-absent hard links. NTFS and standard Linux filesystems are supported; unsupported filesystems fail explicitly. Parent directories must exist. An ordinary publication failure cleans newly created outputs while preserving existing files. Publication is atomic per file; a process interruption may leave a subset of complete JSON/HTML outputs.

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
