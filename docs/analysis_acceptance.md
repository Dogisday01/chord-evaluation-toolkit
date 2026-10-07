# Detailed analysis acceptance criteria

Expected answers are specified before implementation. Analysis is descriptive;
it cannot infer model causes, training quality, song structure or significance.

- On a 10-second C:maj reference with predictions C:maj [0,2], G:maj [2,4],
  C:min [4,6], C:maj [6,8], G:maj [8,10], total disagreement is 6 seconds.
  There are two contiguous error episodes of 4 and 2 seconds, despite three
  confusion regions. C:maj -> G:maj has two occurrences and 4 seconds.
- For that example, C:maj precision is 1, recall .4, F1 4/7. G:maj has no
  reference support, so recall/F1 are null and precision is 0. C:min is likewise.
- Ten equal-duration bins conserve all time and all error-category durations;
  [2,3] has error fraction 1, [0,1] has 0. Splitting equivalent file rows must
  not change the pattern analysis or change boundaries.
- With reference C:maj [0,5], G:maj [5,10] and prediction C:maj [0,5.2],
  G:maj [5.2,10], the +/- .25-second reference-change window is [4.75,5.25].
  It contains .2 error seconds over .5 seconds; outside has 0 over 9.5.
  Overlapping windows are merged before counting. Endpoints are not changes.
- An all-N reference has null chord-only scores, rather than a fabricated
  perfect chord-recognition score. An all-chord reference has null N recall.
- Dataset selection must precede score calculation, with excluded IDs and
  reasons recorded. Do not pick recordings by how well an algorithm performs.
- Imported Harte extensions/inversions are explicitly projected to major/minor
  only when exactly one corresponding triad is present. X and unrepresentable
  qualities fail preparation. Original bytes and SHA-256 hashes are retained.
- Shared coverage uses the shortest end across the declared inputs, records
  every removed tail, and never claims full-recording or official MIREX scores.
- A separate fixed-step oracle on integer-time random examples checks precision,
  recall, temporal bins and total disagreement without calling analysis helpers.
