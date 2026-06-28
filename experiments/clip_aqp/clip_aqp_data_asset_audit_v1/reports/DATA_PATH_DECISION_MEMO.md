# Data Path Decision Memo

## Option A: Build Micro-CASQ adjudicated benchmark from existing local data

- What question it answers: can the project obtain a small, clean `O_enter_ego_path_v0` benchmark without new downloads or full-video VLM scanning?
- Required inputs: existing local videos/clips, old VLM/human/Nexar/candidate tables, bounded adjudication budget.
- Required compute: metadata indexing now; later bounded clip-level VLM only if authorized.
- Human effort: moderate, focused on 50-100 positives, 200-300 negatives, and disagreement cases.
- Risk: pool is biased toward previously explored scenes and may lack diversity.
- Failure condition: too few adjudicated positives with `boundary_status=ok` and recoverable video paths.
- Expected research value: highest immediate value because it directly targets `O_enter_ego_path_v0` and fixes label semantics.

## Option B: Switch to / add DoTA, DADA, or LOTVS-DADA

- What question it answers: whether cleaner external event datasets provide broader and more diverse event-boundary evidence.
- Required inputs: approved dataset acquisition and conversion.
- Required compute: download/storage plus conversion; no need for VLM unless mapping audit is authorized.
- Human effort: lower if labels/boundaries map well, but still requires predicate-mapping audit.
- Risk: access, schema mismatch, or event definitions may not match `O_enter_ego_path_v0`.
- Failure condition: labels lack ego-path conflict semantics or event boundaries.
- Expected research value: important for generalization after Micro-CASQ v0 exists.

## Option C: Keep Nexar only as noisy external-label stress test

- What question it answers: how CASQ tooling behaves under unreliable external labels.
- Required inputs: existing Nexar-200/v2 outputs.
- Required compute: none for this planning pass.
- Human effort: low.
- Risk: cannot support `O_enter_ego_path_v0` oracle-relative claims after the 32B audit found unreliable mapping.
- Failure condition: any report promotes Nexar-derived labels as human truth or oracle truth.
- Expected research value: useful as a stress test, weak as a gold benchmark.

DATA_PATH_RECOMMENDATION: BUILD_MICRO_CASQ_FROM_EXISTING_DATA
