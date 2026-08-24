# T2-C1 Existing-Corpus Descriptive Replay Protocol

## Classification

`C1_SIMULATED_COST_MODEL_RELATIVE_DESCRIPTIVE_ONLY`

## Inputs

- Three videos: DALI, HANGZHOU, WUHAN.
- Two frozen queries per video.
- 2,950 cached 10-second semantic outcomes.
- 1,475 complete query-agnostic YOLOv8n midpoint proxy records.
- Proxy protocol hash:
  `83642c42ed0ab578cdf5db81ccbf29fbcfbd3458b98909c92190fb88920dceab`.

## Frozen semantics

- Every 10-second unit is a candidate by the historical proxy protocol. This run
  cannot measure natural candidate misses.
- Boundary rule: exclude exactly one trailing partial unit per video when its
  duration is below 10 seconds. Any interior partial unit or multiple partial
  units fail validation. This removes 3 proxy units and their 6 query outcomes.
- Proxy score is `0.5 * min(det_count,20)/20 + 0.5 * max_conf`.
- `relevant` units are merged into a model-relative event only when temporally
  contiguous; an unknown, parse failure, or negative breaks continuity.
- `unknown` and `parse_failure` VERIFY calls consume cost and return explicit
  `ORACLE_FAILURE`; they are never converted to negatives.
- Cost tier is C1 with SCAN cost 1 and VERIFY/SCAN ratios `{1,3,10,30}`.
- Deadlines are `{20%,40%,60%}` of exhaustive simulated cost.
- Seeds are the frozen V3 holdout seeds.
- Policies are Sequential, UniformStride, RandomTemporal, LargestGap, DATB-SV,
  and ExSample-EndToEnd-Adapted with chunk counts `{3,6,12}`.
- The ExSample comparator is the predeclared per-row AUC envelope of those chunk
  counts.

## Reporting boundary

The independent statistical support is at most six video-query cells formed from
three videos and two queries. Results are descriptive, model-relative, and based
on simulated costs. No p-value, generalization claim, physical deadline claim,
human-event claim, or natural exposure claim is permitted.
