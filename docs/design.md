# Design and requirements traceability

This package implements a useful evaluation module of the larger chord recognition project. The user operation is: choose reference and prediction files, validate or evaluate, inspect results, save JSON. The actor is a researcher/evaluator using a finished tool. Training and development decisions are not represented as this tool's use cases.

```mermaid
flowchart LR
    User[Researcher or evaluator] --> CLI[Validate or evaluate command]
    CLI --> IO[Read one byte snapshot]
    IO --> Validation[Check labels and chronology]
    Validation --> Evaluation[Align intervals and score]
    Evaluation --> Reporting[JSON and provenance]
    Reporting --> Result[User inspects and saves report]
```

This is an operational flow, not a UML Use Case diagram. The modules share immutable Segment and Annotation records. IO hashes the bytes actually parsed. Validation enforces the input contract, Evaluation delegates named chord comparisons to mir_eval, Reporting records scientific provenance and publishes complete bytes. CLI reports failures to the user.

| Assignment 2 requirement | Evidence in this module | Coverage boundary |
| --- | --- | --- |
| FR-06 Evaluate aligned annotations and export metrics | evaluation.py, reporting.py, exact-answer tests | Reference and predictions are supplied externally |
| FR-05 Valid interval output | Validation of order, positive durations and alphabet; aligned intervals in JSON | Audio inference is not implemented |
| NFR-03 Reproducibility | Input hashes, protocol, dependency/tool versions, optional code revision | Reproduces scoring, not model training |
| UR-01–02 Documented commands | validate/evaluate CLI, README and installed-wheel test | Training and audio-inference commands are outside this module |
| FR-01–04 and NFR-01–02 | Explicitly outside this package | No audio decoding, CQT, baseline/Transformer training or GPU profiling is claimed |

The restricted alphabet prevents unknown chord qualities from silently changing the score denominator. Strict coverage prevents missing predictions from being hidden by clipping or padding. Tiny boundary rounding is recorded instead of silently ignored. Saved reports never overwrite a previous run.

The scientific dependency is mir_eval 0.8.2. Its root and major/minor rules are described in the [official API](https://mir-eval.readthedocs.io/latest/api/chord.html). A broader dataset or chord vocabulary requires a new documented protocol, not merely a more permissive parser.
