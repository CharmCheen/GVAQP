# Candidate-auditor lifecycle incident

Status: `PASS_RECOVERED_EXACT_RECEIPTS_AND_NONMUTATING_VERIFY`.

After Stage A had completed, `audit_mf_psvr_candidate_completion.py --help` exposed that the auditor ignored arguments and always executed its write path. It rechecked a historical pre-oracle condition against the current downstream state, so the legitimate 96-call/192-label manifests and changed stage state were reported as four failures. It then overwrote only three summary artifacts: the completion audit, cost summary, and failures CSV.

The extraction payload did not change. The accidental rerun independently reconfirmed all 603 providers, 2654 units, 5308 query-unit scores, 28551 tracks, source hashes, per-provider hashes, and numeric/content invariants. The original PASS receipt and cost JSON were recovered byte-for-byte from the immutable session tool output; their restored hashes are recorded in the JSON incident audit.

The auditor now has explicit `write` and `verify` stages. `write` refuses to replace an existing PASS receipt. `verify` recomputes stable extraction evidence without rewriting finalized artifacts and treats the zero-oracle-row assertion as historical evidence from the original completion time. A before/after hash-list comparison proved that repaired verification modified no candidate receipt.

Use:

```bash
python scripts/audit_mf_psvr_candidate_completion.py verify
```

Do not rerun the historical write stage after oracle acquisition.
