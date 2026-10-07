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

On the local Windows Python 3.12.14 environment, the suite contains 46 passing pytest cases. The random-grid oracle is one of those cases and includes 30 comparisons. Local lint and format checks pass. Distribution verification installs the actual wheel into a new environment outside the checkout, checks dependency consistency, confirms that the imported package is inside that environment, executes the README example and rejects the invalid-gap fixture without creating a report.

Evidence files are generated under reports/: test-results.xml, distribution-check.json and example-report.json. They are excluded from Git because each run has its own timestamp and provenance. Source tests and verification commands are versioned. The configured GitHub matrix covers Linux Python 3.11/3.12/3.13 and Windows Python 3.12; local Windows evidence does not establish the outcome of those hosted jobs.

Limits: tests verify evaluation behavior on synthetic annotation inputs. They do not establish chord recognition accuracy, dataset access, aligned ground truth quality, training reproducibility or GPU performance. Error messages and preserved reports are also part of observable correctness. Rendering and lint cannot independently prove a scientific score correct.
