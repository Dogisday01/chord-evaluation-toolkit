# Evaluation protocol and future integration

Protocol `major_minor_n_v1` keeps the Assignment 2 root and major/minor metrics.
The vocabulary is explicit major, minor and N, with no inversions. Both timelines
cover the same continuous [0,T]. The shared configuration in protocol.py sets the
1e-9-second normalization tolerance. Unsupported labels and protocols are rejected.
No result silently changes vocabulary, trims time, fills gaps or changes a split.

## What diagnostics mean

Every aligned interval has a duration and label comparisons. Mutually exclusive
error categories are: wrong root; same root with wrong major/minor quality; missed
chord (prediction N); false chord (reference N). Wrong root may include wrong quality.
Adjacent intervals with the same canonical confusion form one error region.
Canonical sharp spellings group enharmonic labels; the original labels remain in
the aligned intervals. A confusion cell counts seconds, not annotation rows.
Recall for a chord is correct seconds / reference seconds. A chord with no reference
support has null recall, rather than an invented zero or perfect score.

Segmentation uses mir_eval overseg, underseg and their minimum, with adjacent
equivalent chords merged first. These are correctness scores: higher is better.
Identical change times can score 1 despite completely wrong chord names. The
scores do not establish a cause such as processing latency or a boundary error.
See the [official rules](https://mir-eval.readthedocs.io/latest/api/chord.html#metrics).

## Collections and comparison

Manifest schema 1.0 declares dataset_id, split (train/validation/test), protocol_id,
models and tracks. Each track has a unique id, reference path and one prediction
path per declared model. Relative paths resolve from the manifest directory;
absolute local paths are accepted. Duplicate JSON keys/IDs, missing predictions,
unknown fields and protocol changes fail before evaluation. All file snapshots are
loaded once per resolved path. Each model uses the same reference snapshot.

Optional model metadata: description, checkpoint_sha256, configuration_sha256,
seed and code_revision. These are caller-supplied declarations, not proof that a
checkpoint was loaded or training reproduced. Input and manifest hashes are
computed from the bytes actually used. The split declaration does not independently
verify dataset separation. During development, use validation for model choices;
test data belongs to the final frozen comparison described in Assignment 2.

Macro averages the per-record scores with equal recording weights. Micro averages
them with duration weights, giving each second equal weight. Both are reported;
they can disagree, so there is no automatic universal winner. Comparison deltas
are candidate minus baseline. Scores range 0-1; a delta 0.10 means 10 percentage
points. Per-record deltas and improved/worsened/tied counts accompany aggregates.
This is a descriptive paired comparison, without a significance claim.

If any declared record/model is invalid or unreadable, the collection is incomplete.
Errors and available individual results remain visible, but all aggregate scores
and comparisons are null. CLI publishes that diagnostic report and returns 2.
Fix the input and create a new run. This prevents silent exclusion from improving
an apparent result. Structural manifest errors produce no report.

## Integration boundary

```python
from chord_eval.api import evaluate_intervals, evaluate_files, run_experiment

report = evaluate_intervals(
    [(0, 8, "C:maj"), (8, 10, "G:maj")],  # reference
    [(0, 8, "C:maj"), (8, 10, "A:min")],  # model adapter output
    code_revision="experiment-identifier",
)
```

The API validates interval triples using the same rules as the file CLI. It accepts
real numeric times and string labels, rather than unchecked internal Annotation
objects. A future audio/model module adapts its frame timing and label mapping
to this contract. It remains responsible for audio processing, configuration,
split/seed records and checkpoint loading. Evaluation does not require a specific
CNN/CRNN/Transformer or a GPU.

In-memory provenance uses canonical JSON of the supplied, pre-normalization triples:
times converted to floats, ensure_ascii=True, separators=(",", ":"), no nonfinite
values. Its hash_representation is canonical_interval_json_v1. File input uses
original_utf8_lab_bytes. These hashes identify different representations and are
not claimed to match even when scores do.

## Reports and compatibility

Schema 1.1 adds kind, diagnostics and protocol ID to the previous pair report.
Existing pair metrics, aligned intervals and CLI commands retain their behavior.
Collection reports are a distinct kind, with models, records, summary and comparison.
The offline HTML embeds the same JSON, uses no external assets and supports recording,
model and interval selection, time windows and embedded JSON viewing. Exported HTML is a
local report artifact, consistent with the optional plots in Assignment 2.

Each output is fully staged and published without overwriting. When publishing JSON
and HTML, an ordinary I/O failure removes outputs newly created by that operation;
existing files stay untouched. Publication is atomic per file, not a transaction
across filesystems: a process interruption can leave a subset of completed files.
