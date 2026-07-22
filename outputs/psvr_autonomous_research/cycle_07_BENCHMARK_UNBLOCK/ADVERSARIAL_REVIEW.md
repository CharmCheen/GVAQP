# Adversarial review

Conclusion: `BENCHMARK_INPUT_POOL=INSUFFICIENT` withstands the alternative explanations checked below.

- The earlier three-file audit was incomplete. This cycle enumerated 604 Nexar paths (603 unique files) and inspected the DrivingDojo archive before deciding.
- Nexar container/stream probing does not repair the fatal workload mismatch: zero clips exceed 60 seconds and each yields at most five 10-second units. Full sequential decode was not claimed or needed after this fatal length screen.
- Different filenames or hashes do not make generated clips independent. Dataset/output/experiment crops remain assigned to their parent derivation groups.
- `realcartest_5k` cannot be promoted because lineage explicitly identifies it as the first 5000 frames of the missing parent.
- Restoring dataset2 would not automatically help: beyond missing bytes, its driver-facing view makes the current road-event ontology inapplicable.
- The canonical heldout `try_or_no/test.mov` is explicitly excluded. Its identity metadata are copied from a pre-existing manifest; no heldout labels, reference, or method result are accessed.
- No configured external mount supplies a usable source; `/mnt/resized_video/archie.mp4` and configured sample paths are absent.
- The 1200-second hard workload screen follows from 29×4 A0 scans and 10-second units; it was not chosen based on candidate-method outcomes.

The main remaining uncertainty is external state: two suitable source videos may be supplied later. That is precisely why the result is an input pause, not scientific NO_GO or a method failure.

## Held-out access disclosure

`HELD_OUT_OPENED=false` means no held-out semantic reference, label, method evaluation, query result, or tuning access. A superseded audit draft did perform a metadata-only `ffprobe` and SHA-256 read of `try_or_no/test.mov` before its canonical-heldout role was recovered. This did not expose evaluator semantics or method performance, but it is still recorded as media-byte metadata access. The final audit and verifier exclude those bytes fail-closed.

## Mandatory adversarial checklist

- More physical oracle calls: N/A; zero calls and zero method runs.
- More GPU-seconds: N/A; no GPU work.
- Eligibility differences: controlled by the frozen 1200-second, provenance, decode, and technical-interface gate.
- Fixed tie-break or event temporal location: N/A to input inventory; the historical tie sensitivity remains a limitation.
- One video/query or final-snapshot-only effects: precisely the unresolved evidence gap, not evidence for a positive method claim.
- Deadline-edge artifact: N/A; no deadline-bound method execution.
- Excluded failures: missing paths, short candidates, duplicates, and derivatives are retained in the candidate/derivation artifacts.
- Runtime/environment drift: no comparative method result was produced; environment and hashes are frozen for reproducibility.
- Future proxy/evaluator-only access: none used for source selection.
- Scheduler overhead: N/A; no scheduler ran.
