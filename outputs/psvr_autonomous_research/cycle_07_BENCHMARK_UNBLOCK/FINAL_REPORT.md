# Cycle 07 — Benchmark Unblock

1. **Active hypothesis:** BENCHMARK_UNBLOCK.
2. **Highest-value uncertainty:** whether two additional independent long local sources exist.
3. **Evidence level:** E3 single-task method evidence; direct Phase-A inventory evidence for input availability does not raise the method-evidence level.
4. **Preregistration:** the user controller froze bounded roots, independence/length gate, no external download, and no heldout evaluation; the artifact precedes the final authoritative audit rerun.
5. **Frozen variables:** existing oracle/reference semantics, 10-second unitization, A0 29×4 scan workload, heldout split.
6. **Changed variables:** none in any method; only candidate input paths were inventoried.
7. **Methods/controls:** no PSVR method executed; source gate compares candidates against frozen eligibility rules.
8. **Changed files:** audit script, Phase-A six-piece evidence package, cycle report, and long-term state ledgers.
9. **Exact command:** `python scripts/audit_psvr_dev_inputs.py`.
10. **Correctness tests:** independent audit verifier 40/40 PASS; `tests/psvr_runtime` 47/47 PASS. Checks cover files, physical hashes/counts, heldout exclusion, new-input reachability, source facts, and decision/state consistency.
11. **Physical run count:** 0; input inventory is prerequisite to physical method experiments.
12. **Primary metrics:** 3 sources required; 1 eligible; 2 missing; 609 candidate rows and 607 existing paths.
13. **Mechanism metrics:** 604 Nexar paths/603 unique; duration range 15.00–49.46 s; zero meet 1200 s.
14. **Cost accounting:** zero GPU-seconds, zero oracle calls, zero proxy calls; CPU filesystem SHA-256, ffprobe, and ZIP-directory inspection only; measured wall time is retained in `raw/AUDIT_EXECUTION.json`.
15. **Winning tasks:** dataset3 is the sole eligible source.
16. **Losing tasks:** no method tasks ran; all other source candidates fail length, provenance, semantics, or presence.
17. **Failure cases:** missing realcartest/dataset2 bytes, derived realcartest prefix, short Nexar/DrivingDojo, excluded heldout.
18. **Adversarial explanation:** inventory omission was falsified by explicitly including Nexar/DrivingDojo; conclusion remained insufficient.
19. **Decision:** `PAUSED_INPUT_REQUIRED`; `PSVR_CORE_INNOVATION=BLOCKED` remains input-caused and is not scientific `NO_GO`; do not continue algorithm work.
20. **Current best observed configuration:** D2 + TB0 ascending + A0, single-task tie-sensitive.
21. **Current best validated method:** null.
22. **Remaining evidence gap:** two independent long sources, then two frozen queries and six valid references/tasks.
23. **Next selected hypothesis:** BENCHMARK_UNBLOCK resumes when files arrive; H-TIE1 remains suspended.
24. **Next exact command:** `python scripts/audit_psvr_dev_inputs.py`.

`docs/PSVR_AUTONOMOUS_RESEARCH_CONTRACT.md` was requested by the controller but is absent in this worktree; it was not fabricated. The supplied controller plus the four existing PSVR documents were used as authority.

`HELD_OUT_OPENED=false` denotes no semantic reference, label, method evaluation, query result, or tuning access. The superseded-draft metadata-only media probe is separately disclosed in `ADVERSARIAL_REVIEW.md` and `AUDITED_DECISION.json`.
