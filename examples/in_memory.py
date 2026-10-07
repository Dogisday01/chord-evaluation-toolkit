"""A future model adapter can pass plain interval triples to the evaluator."""

from chord_eval.api import evaluate_intervals

reference = [(0, 8, "C:maj"), (8, 10, "G:maj")]
prediction = [(0, 8, "C:maj"), (8, 10, "A:min")]
report = evaluate_intervals(reference, prediction, code_revision="adapter-demo")
print(report["metrics"])
