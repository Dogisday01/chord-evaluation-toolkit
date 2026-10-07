# Real MIREX chord annotation demonstration

This example contains published references and algorithm outputs for three real
recordings. No audio, model weights or newly trained predictions are included.
The original bytes are retained in `original`; prepared input is in `prepared`.

Source: [official MIREX 2018 results](https://music-ir.org/mirex/wiki/2018:Audio_Chord_Estimation_Results)
and the linked [algorithm-output repository](https://github.com/ismir-mirex/ace-output/tree/master/2018/Billboard2012).
Downloads are pinned to revision `be7f0e929d3452697f07a227cf1b533426eb2022`.
Ground-Truth is the supplied Billboard2012 benchmark reference. FK2 and JLCX1
are published participant outputs, not this project's own CNN/CRNN/Transformer.

The [McGill Billboard project](https://ddmal.ca/research/The_McGill_Billboard_Project_%28Chord_Analysis_Dataset%29/)
describes the reference annotations and provides the scholarly citation:
John Ashley Burgoyne, Jonathan Wild and Ichiro Fujinaga, *An Expert Ground Truth
Set for Audio Chord Recognition and Music Analysis*, ISMIR 2011, pp. 633-638.
The project releases its annotations under CC0. Its chord times inside phrases
are interpolated; only the first chord of each phrase was aligned by a human.
Therefore reference timing is not independently exact, and boundary-proximity
analysis must be interpreted accordingly. Audio correspondence has not been
independently verified by listening in this project.

Third-party reference and participant output files retain their source provenance.
The toolkit's MIT license covers its own code, not a new licensing claim over
external participant outputs.

## Preparation before evaluation

The preparation rule is frozen before calculating any score:

1. Scan filenames in lexical order. Require all three sources to be continuous
   from zero, projectable and no more than 0.1 s apart at their endpoints.
2. Select the first three eligible IDs: 1006, 1007 and 1011. Earlier IDs 1002,
   1003 and 1009 are excluded for unknown/nontriadic reference labels. Their
   original files and exact reasons remain in the audit. No accuracy-based
   selection or internal time masking is performed.
3. Decode Harte labels. A pitch set must contain exactly one complete major or
   minor triad. Additional tones and bass are discarded; roots use canonical
   sharps. This maps, for example, Db:7 to C#:maj. X, diminished, suspended,
   augmented and ambiguous triads are rejected rather than mapped to N.
4. Use the shortest endpoint across the reference and both predictions, with no
   padding or time shift. Every removed tail is recorded; the maximum is
   0.048979591 s. The prepared extents total 635.095646259 s.
5. Evaluate the prepared files under the unchanged strict major/minor/N protocol.

The split `test` identifies this fixed demonstration from an external benchmark;
it does not prove an independently constructed or representative held-out split
for our future training project. Do not tune future models on these examples and
then report them as a fresh held-out test.

`preparation_audit.json` records selection, exclusions, source URLs/revision,
original and prepared SHA-256 hashes, label mappings, tiny rounding corrections,
common endpoints and removed tail lengths. The manifest supplies preparation
metadata to the HTML report. It is declared metadata; scoring verifies the
actual prepared bytes, not the truth of every external annotation.

## Results and limits

| Published output | Micro root | Micro major/minor | Macro root | Macro major/minor |
| --- | --- | --- | --- | --- |
| FK2 | 94.9687% | 94.6840% | 95.1554% | 94.8794% |
| JLCX1 | 94.7775% | 94.4928% | 94.7283% | 94.4523% |

JLCX1 improves on 1007 and 1011, but worsens on 1006. Its overall major/minor
micro score falls by approximately 0.1912 percentage points. No significance
or universal model ranking follows from these three selected prepared excerpts.
Projection and coverage differ from official MIREX evaluation; these scores
must not be presented as a reproduction of its published corpus results.

After installation, from the repository root:

```text
chord-eval compare examples/real_mirex/manifest.json --baseline FK2 --candidate JLCX1 --output real.json --html real.html
```

This evaluation needs no network. To reproduce preparation from the pinned source,
run `python scripts/prepare_mirex_demo.py --destination NEW_DIRECTORY`. The target
must not already exist. Tests verify exact source/prepared hashes and compare
real-data scores with a separate interval-duration oracle.
