# Reproduction

The builder is preserved for provenance but must not be rerun over this sealed
directory. Verification is read-only:

```bash
python - <<'PY'
import csv, hashlib, json
from pathlib import Path
b = Path('AQP_Algorithm_Invention_Sprint_v1/operator_validation/vlm_heldout_event_enumerate_v2')
for p in b.rglob('*.json'): json.loads(p.read_text())
for p in b.rglob('*.csv'):
    with p.open(newline='') as f: list(csv.reader(f))
for r in csv.DictReader((b/'FILE_MANIFEST.csv').open()):
    assert hashlib.sha256((b/r['relative_path']).read_bytes()).hexdigest() == r['sha256']
print('PASS')
PY
```

This verification does not load Qwen3-VL or execute EVENT_ENUMERATE/VERA.
