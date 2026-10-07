# Extension acceptance criteria fixed before implementation

The v1.0 pair evaluator remains the regression baseline. Existing root/major-minor
scores, strict continuous coverage, vocabulary and no-overwrite behavior must remain
unchanged. This extension continues Evaluation and Reporting/Export in Assignment 2.
Local HTML is an exported diagnostic artifact; there is no hosted application.

## Independent known answers

- C:maj reference against C:min for ten seconds: wrong_quality=10 seconds;
  root=1, major_minor=0. Enharmonic spellings produce no false confusion.
- Reference N against C:maj: false_chord. C:maj against N: missed_chord.
  Wrong-root errors do not imply that chord quality was correct.
- Consecutive identical chords must not introduce segmentation changes. Against
  one ten-second C:maj reference, a genuine five-second C:maj / five-second G:maj
  prediction has overseg=0.5, underseg=1, segmentation=0.5.
- A three-record synthetic collection has durations 10, 4 and 6 seconds. Baseline
  correct root seconds: 8,4,5; correct major/minor seconds: 8,2,5. Candidate: 10,2,5
  for both. Thus baseline micro root=0.85, major_minor=0.75; candidate both=0.85.
  Baseline macro root=79/90, major_minor=32/45; candidate both=7/9.
- Candidate-minus-baseline micro major/minor delta=0.10; macro delta=1/15.
  Per-record quality outcome: one improved, two tied. Root outcome differs.
- An invalid record remains visible with errors. Aggregate scores and comparisons
  are unavailable until all declared records and models are valid. No silent
  dropping of difficult recordings or unmatched model outputs.
- One manifest declares the common track IDs, references, split and protocol.
  Duplicate IDs/JSON keys, missing model predictions and unsupported protocols fail.
- In-memory API and file CLI give the same scores. API inputs pass the same checks;
  its hash describes canonical structured input, not invented original file bytes.
- JSON and offline HTML preserve scores and provenance. HTML uses escaped embedded
  data and text-only insertion for names. Interaction selects tracks/models and
  error intervals. Failed multi-output publication preserves existing files and
  removes outputs newly created by that failed operation.

These criteria are author-defined checks with independent expected values, not
independent human review or evidence of trained-model accuracy.
