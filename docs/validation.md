# Validation method and evidence

The acceptance values were fixed in the preparation specification before implementation. They are computed by counting correct seconds, independently of the functions under test.

| Case | Root | Major/minor | Reason |
| --- | ---: | ---: | --- |
| Exact agreement | 1 | 1 | All ten seconds match |
| Unequal segments, eight correct seconds | 0.8 | 0.8 | 8/10; averaging two rows would give the wrong 0.5 |
| One-second boundary error | 0.9 | 0.9 | Correct on [0,4) and [5,10) |
| C major versus C minor | 1 | 0 | Same root, different quality |
| C major versus G major | 0 | 0 | No time matches |

Additional tests cover no-chord N, enharmonic roots, blank/BOM text, snapshot hashes, boundary rounding, incompatible coverage, invalid/unsupported labels, encoding failures, CLI exit codes and failed/non-overwriting report publication. The input error suite checks negative/nonfinite times, gaps, overlaps, unsorted data and intervals collapsed by rounding.

A separate deterministic oracle generates 30 pairs with integer-second boundaries. It expands each interval to per-second labels and counts matching roots and qualities. It does not call the package's temporal alignment or mir_eval comparisons to calculate expected results. Splitting equal-label intervals and positive time scaling are checked separately.

On the local Windows Python 3.12.14 environment, the suite contains 107 passing pytest cases (46 legacy, 38 version 1.1 extension and 23 version 1.2 analysis/data cases). The original random-grid oracle includes 30 comparisons; a separate analysis oracle checks 30 additional pairs. Local lint and format checks pass. Distribution verification installs the actual wheel into a new environment outside the checkout, checks dependency consistency, confirms that the imported package is inside that environment, executes the README example and rejects the invalid-gap fixture without creating a report.

Evidence files are generated under reports/: test-results.xml, distribution-check.json and example-report.json. They are excluded from Git because each run has its own timestamp and provenance. Source tests and verification commands are versioned. The configured GitHub matrix covers Linux Python 3.11/3.12/3.13 and Windows Python 3.12; local Windows evidence does not establish the outcome of those hosted jobs.

Limits: synthetic tests verify known answers and real-data tests verify source/prepared hashes and scoring on three prepared benchmark excerpts. They do not establish independently exact ground truth, representative corpus performance, our own model accuracy, training reproducibility or GPU performance. Error messages and preserved reports are also part of observable correctness. Rendering and lint cannot independently prove a scientific score correct.


Version 1.1 adds independently specified error categories, enharmonic confusion
normalization, no-support recall, repeated-label segmentation invariance and the
counterexample where segmentation=1 but chord accuracy=0. Collection fixtures have
hand-counted correct seconds (8,4,5)/(8,2,5) for baseline root/quality and (10,2,5)
for the candidate. They verify both macro and micro scores and paired deltas.
Missing/malformed predictions suppress aggregates rather than improving a result
by exclusion. Manifest ambiguity, API validation, safe HTML embedding and ordinary
multi-output failure rollback have explicit negative cases.

The installed-wheel verifier additionally runs collection comparison and offline
HTML export, proving the template resource is packaged, and calls the public
interval API. Browser QA checks recording/model selection, an error-row detail,
time-window controls and embedded JSON viewing against the generated report. A local
preview server is only a QA aid; the final HTML works directly as an offline file.

Acceptance criteria and expected values were fixed before coding in
extension_acceptance.md. Model metadata and split declarations are retained but
not independently verified. There is no automatic model-winner or significance
claim. No training or checkpoint reload is demonstrated by these synthetic runs.

Version 1.2 uses [predefined analysis acceptance criteria](analysis_acceptance.md)
for error episodes, precision/recall/F1, temporal partitions, overlapping boundary
windows and unavailable denominators. A separate oracle walks real prepared input
intervals and counts matching label/root seconds without calling toolkit scoring
or analysis helpers. Imported original/prepared file hashes and selection exclusions
are checked offline. The installed-wheel verifier also evaluates the real demo.
