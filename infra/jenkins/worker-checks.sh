#!/bin/sh
set -eu
mkdir -p /tmp/results
chord-eval --version
chord-eval evaluate /tmp/examples/reference.lab /tmp/examples/prediction.lab \
    --output /tmp/results/known.json --html /tmp/results/known.html --code-revision "$CODE_REVISION"
chord-eval compare /tmp/examples/real_mirex/manifest.json --baseline FK2 --candidate JLCX1 \
    --output /tmp/results/real.json --html /tmp/results/real.html --code-revision "$CODE_REVISION"
python - <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path

assert os.getuid() == 10001, 'Runtime must run as the dedicated non-root user'
known = json.loads(Path('/tmp/results/known.json').read_text())
assert math.isclose(known['duration_seconds'], 10.0)
for metric in ('root', 'major_minor'):
    assert math.isclose(known['metrics'][metric], 0.8, abs_tol=1e-12), metric
for role, name in [('reference', 'reference.lab'), ('prediction', 'prediction.lab')]:
    expected = hashlib.sha256(Path('/tmp/examples', name).read_bytes()).hexdigest()
    assert known['inputs'][role]['sha256'] == expected
assert known['tool']['code_revision'] == os.environ['CODE_REVISION']
real = json.loads(Path('/tmp/results/real.json').read_text())
assert real['status'] == 'complete'
assert len(real['records']) == 3
assert set(real['summary']) == {'FK2', 'JLCX1'}
expected = {'FK2': 0.9468402950967814, 'JLCX1': 0.944928179956164}
for model, score in expected.items():
    assert math.isclose(
        real['summary'][model]['micro']['major_minor'], score, rel_tol=0, abs_tol=1e-12
    ), model
assert real['tool']['code_revision'] == os.environ['CODE_REVISION']
for name in ('known.html', 'real.html'):
    assert Path('/tmp/results', name).stat().st_size > 1000
print('Runtime smoke passed: non-root, both known metrics=0.8, hashes, real 3-record report, HTML')
PY
# Invalid data and existing output both must fail without replacing the report.
printf '0 1 invalid:quality\n' > /tmp/invalid.lab
invalid_status=0
chord-eval evaluate /tmp/invalid.lab /tmp/examples/prediction.lab \
    --output /tmp/results/invalid.json || invalid_status=$?
test "$invalid_status" -eq 2
test ! -e /tmp/results/invalid.json
known_hash=$(sha256sum /tmp/results/known.json)
overwrite_status=0
chord-eval evaluate /tmp/examples/reference.lab /tmp/examples/prediction.lab \
    --output /tmp/results/known.json || overwrite_status=$?
test "$overwrite_status" -eq 3
test "$known_hash" = "$(sha256sum /tmp/results/known.json)"
echo 'Negative checks passed: invalid input=2 with no report; overwrite=3 with unchanged bytes'
