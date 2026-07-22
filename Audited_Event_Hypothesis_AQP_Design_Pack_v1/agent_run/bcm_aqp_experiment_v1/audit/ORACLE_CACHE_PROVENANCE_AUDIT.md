# Oracle Cache Provenance Audit

Audit date: 2026-07-10 UTC  
Final decision: `ORACLE_PROVENANCE_BLOCKED_REQUIRES_BENCHMARK_V2`

No VLM was loaded or called.  No clean-baseline file was modified.  No BCM,
canonical, exploratory, ablation, ceiling, baseline, or synthetic experiment
was implemented or run.  The only video operation was deterministic read-only
replay of the recovered cache-generation frame loader for provenance hashing.

## Strongest supported conclusion

The unit-346 cache was requested for a genuinely different input interval from
the frozen unit-346 interval.  A current-environment replay of the exact
recovered selection/loader code also produces a different frame sequence.  This
is not merely a formatting mismatch or high overlap:

| Field | Frozen unit 346 | Original raw-cache unit 346 |
|---|---:|---:|
| requested interval | `[3457.930000, 3462.930000]` | `[3457.866000, 3462.866000]` |
| OpenCV requested/decoded start index | `103737` | `103735` |
| sample step | 15 frames | 15 frames |
| decoded sampled indices | `103737, 103752, …, 103872` | `103735, 103750, …, 103885` |
| sampled frame count | 10 | 11 |
| aggregate decoded-index hash | `08b47be31f1786f29c5ba95532f235e364d38dd2f4aff25a60a3c9bd25dc92b9` | `0415d410de669ac034a34db73a2b70f31e1cf3e7f52dc1fd51c4ccb0e55f0e2e` |
| aggregate RGB-content hash | `c48f748eb5ea77059935e9ca199eae7f752d8859266a0f57f2e3314d8283d61f` | `72a804ea32028c5493a578f3410a2f07c4f09ac7dda74a3e1d65a2d27f626f2e` |

All 10 position-aligned pairs in the current OpenCV 4.13 exact-code replay have
different decoded indices, timestamps, and RGB content hashes, and the cache
sequence has an additional final frame at index 103885.  Exact per-frame
evidence is in
`unit346_frame_equivalence.csv`.

Generation-time decoder versions and decoded arrays were not retained, so the
RGB hashes are current exact-code replay evidence rather than cryptographic
hashes of historical in-memory arrays.  The requested intervals and the
source-code frame-index arithmetic are primary historical artifacts and already
establish a genuinely different cache input.  The required decision follows:
the old frozen baseline cannot be
mixed with an oracle corrected to the frozen interval.  A new benchmark ID and
a compatible baseline rerun are required.  Query frequency and downstream
metrics do not alter this compatibility decision.

## Recovered original cache-generation lineage

The clean benchmark copied 347 raw responses from two mutually exclusive
sources:

| Source | Units | Authoritative generation script | SHA256 |
|---|---:|---|---|
| Stage-2 full scan | 297 | `src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/scripts/stage2_full_center10_oracle.py` | `1e1c45ce88027698cc3c3fce2aca31e3c0975b9e99348197b2022b36c31e6974` |
| P1 pilot reused by Stage 2 | 50 | `src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/run_pilot_oracle.py` | `b719b262c64a2b323e61c5f493642be26d232bfdaf15cbc2b87fdd8f9350a07a` |

Unit 346 is a Stage-2 full-scan response.  Source membership is exhaustive:
297 JSON files exist only in `raw_per_anchor_full`, 50 exist only in the P1
`raw_per_anchor`, no frozen unit is missing, and no unit has both sources.

Both scripts use the same frame-selection and loading procedure:

```text
video_fps = cv2.VideoCapture(video).get(CAP_PROP_FPS)
start_frame = int(clip_start * video_fps)
end_frame = int(clip_end * video_fps)
cap.set(CAP_PROP_POS_FRAMES, start_frame)
frame_interval = max(1, int(video_fps / 2.0))
for fi in range(start_frame, end_frame + 1):
    ret, frame = cap.read()
    if not ret: break
    if (fi - start_frame) % frame_interval == 0:
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
```

If fewer than five frames are returned, both scripts retry with target `fps=4`;
that branch is not reached for any compared 10-second unit or unit 346 under
the recovered source video.  Frames are converted to PIL images, passed as a
video with message `fps=2.0`, and processed by `process_vision_info` and the
Qwen processor.

The audit instrument `reproduce_oracle_provenance.py` preserves the loop above.
Its only additions after each `cap.read()` are recording OpenCV’s decoded
position/timestamp and hashing the selected RGB array.  It contains no model
import or generation call.  Reproduction manifest:
`provenance_reproduction_manifest.json`.

## All-unit comparison

`oracle_cache_interval_audit.csv` has exactly 347 rows, one per frozen unit, and
includes video hash, unit/anchor ID, both requested intervals, deltas, requested
and decoded frame indices, decoded timestamps, frame counts, aggregate hashes,
source script/hash, model/prompt/parser fields, raw-response hashes, and a
per-unit decision.

Observed summary:

| Check | Result |
|---|---:|
| video SHA256 matches frozen/source manifest | 347/347 |
| raw response present and source/frozen/manifest hash identical | 347/347 |
| prompt hash matches | 347/347 |
| interval deltas exactly zero | 346/347 |
| decoded frame-index sequence identical | 346/347 |
| decoded RGB-content sequence identical | 346/347 |
| differing unit | 346 only |

Rows 0–345 are marked `ORACLE_PROVENANCE_UNRESOLVED`, not content-equivalent
approved, because generation-time model bytes, package versions, processor
hash, video-processor hash, and full generation hash were not recorded by the
original calls.  Current paths/config files and declared lineage agree, but a
same current path is weaker than contemporaneous cryptographic provenance.
This conservative per-row status does not weaken the global result: unit 346
has directly different selected indices and contents and therefore triggers the
stronger benchmark-v2 decision.

## Exact source of the 0.064-second mismatch

The root cause is a mixed MP4 duration field followed by final-anchor clipping:

1. The original anchor builder
   `src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/build_anchor_plan.py`
   (SHA256 `eb447f5139fd9c1d864dac4d794c2de5487459d466f0ad4e3ae8f450978e1eaf`)
   hard-codes `VIDEO_DURATION = 3462.866` (line 18).  That equals the current
   video-stream duration reported by ffprobe.
2. The clean proxy precompute
   `outputs/video_feature_precompute_v1/scripts/precompute_video_features.py`
   (SHA256 `0a878d23c5f0500160e098a517142e38ab67f83c0fff25a1c1667094a73ca69e`)
   asks ffprobe for `format=duration` and sets `duration_seconds` from
   `raw["format"]["duration"]` (lines 64–93).  The MP4 format duration is
   `3462.930499`.
3. Both anchor builders compute the last anchor with `anchor_time=min(duration,
   i*10+5)`, then `[anchor_time-5, min(duration,anchor_time+5)]`, and format to
   three decimals.  Only the clipped final anchor changes: `3462.866` becomes
   `3462.930`, shifting both endpoints by `0.064` seconds.
4. The original loader uses OpenCV’s runtime FPS `30.000005775562784` and
   truncates `time*fps` with `int`.  Thus cache start 3457.866 maps to requested
   index 103735, while frozen start 3457.930 maps to 103737.  This propagates
   the metadata discrepancy into different actual input frames.
5. The cache end maps to 103886 and the frozen end to 103887, both beyond the
   last valid decoded index 103885.  EOF plus the different sampling phase
   gives 11 cache frames versus 10 frozen frames.

### Candidate-cause adjudication

| Candidate cause | Decision | Evidence |
|---|---|---|
| float formatting | not root cause | Three-decimal formatting preserves an upstream 0.064-second difference; it does not create it. |
| ffprobe/container duration difference | root cause | stream duration is 3462.866; format duration is 3462.930499; the two builders use those different values. |
| final-unit clipping | necessary mechanism | only unit 346 is duration-clipped and only unit 346 differs. |
| FPS rational conversion | propagation factor, not root | common OpenCV FPS maps the shifted times to indices two apart. |
| frame-index rounding | propagation factor | both scripts use truncating `int`; the different inputs cross two frame boundaries. |
| anchor-centered clip generation | necessary mechanism | final `min(duration, …)` moves both center/end and start. |
| separate video-loader behavior | rejected | P1 and Stage-2 use the same recovered OpenCV loop; unit 346 is Stage-2. |
| stale metadata | no evidence | the discrepancy is reproducibly explained by choosing format rather than stream duration from the same MP4, not by an unidentified stale file. |
| different video bytes | rejected | SHA256 `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610` matches all 347 frozen rows/manifests. |
| another cause | unnecessary | the duration-field choice fully predicts the sole interval and frame mismatch. |

## Configuration and response provenance

| Item | Evidence | Audit result |
|---|---|---|
| video | direct SHA256 over current MP4 and frozen manifest | exact match, `bad229…f610` |
| model | both source scripts use the same Qwen3-VL-32B path; frozen current-manifest hash is `921540…f0ea` | same path/current manifest, but no generation-time weight hash; unresolved |
| processor | both use `AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)`; reconstructed current config hash `c8b443…9248` | no generation-time processor/package hash; unresolved |
| video processor | exact OpenCV selection loop recovered; reconstructed config hash `409e67…7fc7` | original OpenCV/qwen-vl-utils versions not recorded; code path recovered, environment hash unresolved |
| generation | both explicitly call `generate(max_new_tokens=256, temperature=0.1)`; reconstructed config hash `135a37…b766` | full generation defaults/library versions not recorded; unresolved |
| prompt | both scripts point to the frozen prompt; direct SHA256 `121874…f33` | exact current artifact/manifest match |
| parser | P1 uses regex `\{[^{}]*\}`; Stage-2 uses `\{.*\}`; source-file hashes differ; frozen declaration hash is `2b0c34…bb30` rather than a source hash | heterogeneous implementation and no generation-time parser hash; unresolved as a hash comparison |
| raw response | nested `raw` model text is hashed separately; every nested source/frozen hash agrees; the original source JSON, frozen envelope, and cache-manifest envelope SHA also agree | nested response and envelope present/exact for 347/347; both hashes are recorded separately in the interval CSV |

The parser heterogeneity is a separate provenance limitation.  It does not
excuse or cause unit 346’s frame mismatch, and output-label quality is not used
in the compatibility decision.

## Was unit 346 queried?

Counts below are run/budget instances in the frozen aggregate action traces.
`call_idx` is zero-based; the human call number is `call_idx+1`.  Native and
controlled rows for a shared adapter/random order are separately materialized
run instances, so combined counts intentionally include both.  Full evidence is
in `unit346_query_usage.csv`.

| Requested family/track | Runs containing unit 346 / total runs | Earliest budget | Earliest call index (number) |
|---|---:|---:|---:|
| current M0 | 0 / 6 | — | — |
| current M1 | 0 / 6 | — | — |
| native ARC | 13 / 30 | 50 | 21 (22nd) |
| controlled ARC | 13 / 30 | 50 | 21 (22nd) |
| SUPG, all native/controlled variants | 0 / 120 | — | — |
| ABae native | 3 / 30 | 80 | 23 (24th) |
| ABae controlled | 3 / 30 | 80 | 23 (24th) |
| random native | 67 / 600 | 5 | 0 (1st; seed 66) |
| random controlled | 67 / 600 | 5 | 0 (1st; seed 66) |
| all controlled traces replayed under both materializers | 83 / 732 | 5 | 0 (1st) |

The 83 affected controlled traces comprise 67 random, 13 ARC, and 3 ABae
traces.  Every affected controlled trace has a corresponding row in
`comparisons/materializer_replay_comparison.csv`; B1 top-proxy, B2
component-first, and B4 SUPG contribute zero.  Replay does not make a new
physical VLM call, but it consumes the incompatible cached observation when the
trace queries unit 346.

Again, this usage is diagnostic only.  Even if every count were zero, the
strict interval/cache compatibility claim would still be false.

## Final provenance decision

`ORACLE_PROVENANCE_BLOCKED_REQUIRES_BENCHMARK_V2`

Decisive evidence: primary raw artifacts record different requested intervals,
and the exact recovered arithmetic selects a different index phase.  Current
OpenCV 4.13 exact-code replay confirms different frame counts, timestamps, and
RGB contents for unit 346 under those intervals.

Main competing explanation: that 0.064 seconds is harmless metadata drift.
It is rejected because the drift crosses frame-index boundaries and changes
every sampled frame.

Required next action (not authorized or performed here): define a benchmark-v2
unit grid with one authoritative duration convention; generate/reuse only an
oracle proven compatible with that grid; bind model/processor/video-processor/
generation/parser environment hashes at call time; assign a new benchmark ID;
and rerun compatible baselines before any BCM comparison.

Rejection/revision condition: this decision could be revised only by primary
generation evidence proving that the VLM for unit 346 actually received the
frozen 103737-phase frame sequence despite the recovered source code and raw
interval.  No such evidence exists in the repository; the existing artifacts
show the opposite requested interval.
