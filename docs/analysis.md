# Descriptive analysis definitions

Report schema 1.2 adds an `analysis` object to each pair and to complete model
summaries. Core scores and the `major_minor_n_v1` protocol retain their previous
meaning. HTML accepts 1.1 and 1.2 reports; older reports have no added analysis.

Every measure counts time in seconds. Canonical enharmonic labels are used for
grouping. Original aligned labels remain in JSON. Numerical results are computed
from intervals, without sampling or generated explanations.

| Analysis | Definition and interpretation |
| --- | --- |
| Disagreement fraction | All nonmatching major/minor time divided by evaluated duration. |
| Error episodes | Contiguous nonmatching time, merged even when the wrong chord changes. A correct passage separates episodes. Mean, median and longest episode describe their lengths. |
| Confusion patterns | A reference/prediction label pair, its total seconds, number of separate same-pair regions and fraction of all error time. The HTML shows the largest ten; JSON retains all. |
| Root offsets | Prediction root minus reference root modulo 12, counted only on wrong-root regions. N is excluded. This is a substitution pattern, not evidence of a key or a cause. |
| Per-chord precision | Correct seconds / predicted seconds for that chord. Null when never predicted. |
| Per-chord recall | Correct seconds / reference seconds for that chord. Null without reference support. |
| Per-chord F1 | 2PR/(P+R), zero when both defined and zero; null when either precision or recall is unavailable. Supports are retained so short passages are visible. |
| Temporal bins | Ten equal-duration, half-open windows, ending at T. Each reports category seconds and error fraction. Partial intervals contribute their overlap duration. |
| Boundary proximity | Union of +/-0.25-second windows around internal canonical reference chord changes, clipped to [0,T]. Near and away error fractions use their own duration denominators. Endpoints and duplicate equivalent labels are not changes. Null when no time is available. |
| Reference slices | Chord-only root/major-minor agreement excludes reference N. N recall counts correct N seconds / reference N seconds. Predicted N during a reference chord remains an error. N need not mean acoustic silence. |
| Collection patterns | Pool confusion seconds/region counts and report the number of recordings affected. Minimum, median and maximum scores give each recording equal weight. Incomplete collections have no summaries. |

Findings are deterministic sentences describing measured quantities. They do not
diagnose processing latency, poor training, overfitting, tonal function, verse/chorus
structure or statistical significance. Boundary proximity is sensitive to the
reference timing precision and the fixed 0.25-second radius. This release does not
perform a sensitivity study or boundary-to-boundary event matching.

Overall, chord-only, near-boundary and away-boundary percentages use different
denominators. Their percentages must not be added. Category seconds and temporal
bin seconds partition the evaluated time; overlapping boundary windows never
double-count it. Small cohorts and rare chords do not establish general model
performance.

For extreme floating-point inputs, a time bin with zero representable duration
has an unavailable error fraction. It is disabled in the interactive map.

The [acceptance criteria](analysis_acceptance.md) and tests include known answers,
an independent integer-time oracle, overlapping-window counterexamples, all-N
inputs, equivalent-row splitting and a separate real-data interval oracle.
