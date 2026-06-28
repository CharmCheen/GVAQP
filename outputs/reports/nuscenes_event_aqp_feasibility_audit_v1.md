# nuScenes Event-AQP Feasibility Audit v1

Generated: 2026-06-18

## Scope

Task: judge whether nuScenes can serve as a public, query-conditioned, geometry-grounded event-AQP benchmark source, and design the minimum viable adapter schema.

This is a read-only asset audit and design note. No nuScenes data was downloaded, no model was run, no training was performed, and no VLM inference was called. The conclusions below are based on public nuScenes documentation and the current G-ARC repository shape.

Decision: `PARTIAL_GO`

Rationale: nuScenes exposes enough public geometry, annotation, ego-pose, map, and optional CAN bus fields to define offline geometry-derived event labels for several traffic-interaction queries. It is not yet a full `GO` because event rates, threshold stability, and ambiguity levels must be measured on `v1.0-mini` before claiming a non-degenerate benchmark.

## Public Assets Checked

| Asset | Public status | Relevance |
|---|---|---|
| nuScenes devkit | Public and installable via `nuscenes-devkit`; official README states devkit setup and dataset folder layout. | Provides Python APIs, schema access, maps, prediction helpers, and evaluation-related utilities. |
| Schema | Public. The relational schema includes `scene`, `sample`, `sample_annotation`, `ego_pose`, `sample_data`, `calibrated_sensor`, `log`, `map`, `instance`, `attribute`, and `visibility`. | Sufficient for geometry-derived event labels at annotated keyframes. |
| Sample annotations | Public with dataset metadata. `sample_annotation` gives global 3D box center, size, rotation, instance token, visibility, lidar/radar point counts, and prev/next links. | Core offline event-GT source for actor trajectory and interaction geometry. |
| Scene/log relation | Public. A scene is a 20s sequence from a log; multiple scenes can come from the same log. Instance identities are not preserved across scenes. | Supports stream grouping by log, but forbids cross-scene actor identity continuity. |
| Maps | Public expansion. Devkit README describes semantic map layers and v1.2/v1.3 additions including arcline paths, lane connectivity, and lidar basemap support. | Useful for path, lane, drivable-area, and corridor queries. |
| CAN bus expansion | Public optional expansion. Includes ego pose, velocity, acceleration, steering, yaw rate, turn signals, brake/throttle, and route snippets. Official docs call it highly experimental; route is missing for about 3% of scenes. | Useful for ego-maneuver and future-corridor refinement, but should be optional in v1. |
| License / access | Dataset requires nuScenes account and Terms of Use; official/public materials describe non-commercial/research use. The devkit code is separately public. | Reproducible academic benchmark is plausible; commercial use needs separate terms. |

Key public facts to treat as hard constraints:

- `sample` is an annotated keyframe at 2 Hz.
- `scene` is a 20s sequence.
- Object `instance_token` is tracked within a scene but not across scenes.
- `ego_pose` is in the global coordinate system of the log map; x-y localization is 2D and z is always 0.
- `sample_annotation` locations are global 3D boxes at the sample level, not camera-frame detections.
- CAN bus pose is available at 50 Hz and IMU/steering channels are higher frequency, but CAN bus is marked experimental.

Sources checked:

- nuScenes schema: https://raw.githubusercontent.com/nutonomy/nuscenes-devkit/master/docs/schema_nuscenes.md
- nuScenes devkit README: https://raw.githubusercontent.com/nutonomy/nuscenes-devkit/master/README.md
- CAN bus README: https://raw.githubusercontent.com/nutonomy/nuscenes-devkit/master/python-sdk/nuscenes/can_bus/README.md
- Prediction tutorial: https://www.nuscenes.org/tutorials/prediction_tutorial.html
- Map expansion tutorial: https://www.nuscenes.org/tutorials/map_expansion_tutorial.html
- nuScenes Terms: https://www.nuscenes.org/terms-of-use

## Query Feasibility

All event labels below must be constructed offline from public geometry annotations. They are evaluation labels, not online scheduling features.

### 1. Vehicle Enters Ego Future Corridor

Goal: detect actors that enter a buffered ego future corridor.

Required fields:

- `sample.timestamp`, `sample.next`, `sample.prev`
- `scene.token`, `scene.name`, `scene.log_token`
- `ego_pose.translation`, `ego_pose.rotation`
- `sample_annotation.instance_token`, `translation`, `size`, `rotation`, `category_token`, `visibility_token`
- Optional: map lane/arcline path, CAN bus route, CAN bus 50 Hz ego pose

Offline formula:

1. For each sample time `t`, form an ego future path over horizon `H` seconds from future ego poses in the same scene. Default smoke values: `H = 3s` and `H = 5s`.
2. Convert ego path points to a corridor polygon by buffering the polyline by `corridor_half_width`, default `1.5m` to `2.5m`.
3. For each vehicle actor, compute whether its box center or footprint intersects the corridor.
4. Mark an event when the actor is outside the corridor at `t0` and inside at a later sample `t1`, with entry sustained for at least one subsequent keyframe when possible.

Time resolution:

- Baseline actor state: 2 Hz from `sample_annotation`.
- Optional ego corridor refinement: 50 Hz CAN bus pose, but actor state remains 2 Hz unless interpolation is added.

Ambiguities:

- Uses realized future ego path, so labels must remain offline evaluation only.
- Actor footprint may enter corridor while object is not visually visible in a front camera.
- Sparse 2 Hz actor state can miss short crossings or create threshold sensitivity.
- Corridor width and horizon need calibration on mini.

Feasibility: high for offline evaluation, medium for visual candidate coverage because camera visibility and geometry label may diverge.

### 2. Vehicle Crosses Ego Path

Goal: detect actors whose trajectory crosses the ego path.

Required fields:

- Same base fields as query 1.
- Actor trajectory from chained `sample_annotation.prev/next` within one scene.
- Ego trajectory from `ego_pose` over the same interval.
- Optional map lane direction and lane connector information.

Offline formula:

1. Build ego path polyline from ego positions over `[t - h_past, t + h_future]`.
2. Build actor trajectory polyline from actor box centers over the same window.
3. Compute either:
   - segment intersection between actor path and buffered ego path, or
   - sign change across ego path centerline plus minimum distance below `d_cross`.
4. Mark an event interval from first near/intersecting sample to last conflicting sample.

Time resolution:

- 2 Hz actor and ego annotations are enough for coarse crossing labels.
- CAN bus can refine ego path but cannot refine actor trajectory without interpolation.

Ambiguities:

- Turning and lane-change interactions can look like crossing depending on corridor definition.
- Parallel adjacent lanes can trigger false positives if buffer is too wide.
- Geometry crossing may happen outside camera view; visual benchmark should record camera visibility separately.

Feasibility: high for geometry benchmark, with threshold tuning required.

### 3. Close Approach / Relative Closing

Goal: detect vehicles that approach the ego vehicle with small predicted separation and positive closing speed.

Required fields:

- Ego pose sequence from `ego_pose`; optional ego velocity from CAN bus pose/vehicle monitor.
- Actor box centers from `sample_annotation.translation`.
- Actor velocity from finite differences over annotations, or devkit helper if available in implementation.
- Actor size/yaw for footprint distance rather than center distance.

Offline formula:

For actor position `p_a`, ego position `p_e`, actor velocity `v_a`, and ego velocity `v_e`:

- `r = p_a - p_e`
- `v_rel = v_a - v_e`
- `closing_rate = -dot(r, v_rel) / max(norm(r), eps)`
- `tca = clamp(-dot(r, v_rel) / max(norm(v_rel)^2, eps), 0, H)`
- `d_tca = norm(r + v_rel * tca)`

Positive event if:

- current distance or footprint distance is below `d_near`, or
- `d_tca < d_tca_thresh` and `closing_rate > v_close_thresh`.

Default smoke thresholds to calibrate: `d_near = 8m`, `d_tca_thresh = 5m`, `v_close_thresh = 1m/s`, `H = 3s`.

Time resolution:

- 2 Hz is acceptable for smoke, but derivative estimates are noisy.
- CAN bus 50 Hz ego velocity is preferred when available.

Ambiguities:

- Finite-difference actor velocity at 2 Hz is noisy.
- Parked or stopped vehicles can be close but not a closing threat.
- Center distance can overstate/understate footprint distance; footprint distance is preferred.

Feasibility: medium-high, but requires sanity checks for noisy velocity and parked actors.

### 4. Ego Maneuver With Interacting Object

Goal: detect ego maneuvers that co-occur with a nearby or path-conflicting actor.

Required fields:

- Ego yaw from `ego_pose.rotation`.
- Ego speed and acceleration from finite differences or CAN bus pose/vehicle monitor.
- Optional CAN bus steering, yaw rate, brake, turn signals, throttle.
- Actor positions and trajectories from `sample_annotation`.
- Optional map lane and lane connector context.

Offline formula:

1. Detect ego maneuver windows:
   - lane/turn: `abs(yaw_rate) > yaw_thresh` or steering magnitude above threshold;
   - braking: deceleration below threshold or brake active;
   - lateral maneuver: lateral displacement relative to previous heading above threshold.
2. Identify interacting objects:
   - actor within distance threshold; or
   - actor intersects ego future corridor/path; or
   - actor is in same/adjacent lane with closing geometry.
3. Event is positive when ego maneuver and interacting-object condition overlap for at least one keyframe.

Time resolution:

- Best with CAN bus at 50 Hz or 100 Hz for maneuver onset.
- 2 Hz ego pose can support coarse smoke but may miss short control actions.

Ambiguities:

- Causality cannot be proven from geometry alone.
- Ego may maneuver for road geometry, traffic lights, or unseen objects.
- This should be described as "maneuver with nearby/path-conflicting object", not true behavioral intent.

Feasibility: partial. Good for an engineering benchmark, weak for semantic causal claims.

## Stream Construction

nuScenes scenes are only 20s long, but G-ARC and AQP experiments need longer ordered streams. The safe construction is:

1. Group scenes by `log_token`.
2. Sort scenes by their first sample timestamp within each log.
3. Assign `stream_id = log_token` or `location/date/logfile` if available through `log`.
4. Keep `source_video = scene.name` for source-video grouped splits and leakage checks.
5. Within each scene, define intervals using seconds from the first sample timestamp.
6. Across scenes, allow stream-level retrieval metrics but do not merge event intervals or actor identities across scene boundaries.

Identity rule:

- `actor_instance_id` is valid only within one scene.
- For cross-scene stream concatenation, store `actor_instance_id = scene_token + ":" + instance_token`.
- Do not treat identical-looking actors across scenes as the same entity.

Event-boundary rule:

- Default: no event can span a scene boundary.
- A future extension may allow geometry-only scene-boundary intervals with `actor_instance_id = null`, but that should not be part of the smoke benchmark.

## Minimum Adapter Schema

The adapter should materialize one interval-level table. A frame/sample-level table can be produced internally, but AQP should consume intervals and cheap candidate records.

Required identity and timing columns:

| Column | Meaning |
|---|---|
| `scene_id` | nuScenes `scene.token` or `scene.name`; stable scene identifier. |
| `stream_id` | log-level stream grouping, preferably `log_token`. |
| `source_video` | scene-level grouping key for splits and leakage checks, default `scene.name`. |
| `interval_id` | Unique adapter-generated event or candidate interval id. |
| `event_type` | Query name, e.g. `future_corridor_entry`, `crosses_ego_path`, `close_approach`, `ego_maneuver_interaction`. |
| `event_start` | Seconds from scene start or absolute Unix microseconds normalized to seconds; choose one and record units. |
| `event_end` | Same unit as `event_start`. |
| `actor_instance_id` | `scene_token:instance_token`; null only for ego-only intervals. |

GT geometry fields, evaluation-only:

| Column | Meaning |
|---|---|
| `gt_actor_category` | nuScenes category name. |
| `gt_actor_visibility` | Visibility token/level for later visual feasibility analysis. |
| `gt_actor_translation_xy` | Actor center path or representative x-y sequence. |
| `gt_actor_velocity_xy` | Finite-difference actor velocity sequence. |
| `gt_actor_box_size` | Width, length, height. |
| `gt_actor_yaw` | Actor yaw sequence. |
| `gt_ego_translation_xy` | Ego path sequence. |
| `gt_ego_yaw` | Ego yaw sequence. |
| `gt_ego_speed` | Ego speed sequence from pose differences or CAN bus. |
| `gt_min_distance` | Minimum actor-ego center or footprint distance over interval. |
| `gt_ttc` | Estimated time-to-closest-approach / time-to-collision proxy. |
| `gt_path_intersection` | Boolean or score for actor path intersecting ego path. |
| `gt_corridor_entry` | Boolean or score for outside-to-inside corridor transition. |
| `gt_label` | Offline positive label for the query. |

Cheap online candidate/proxy fields:

| Column | Meaning |
|---|---|
| `cheap_vehicle_count` | Count from lightweight detector or existing projected annotations in oracle-free smoke. |
| `cheap_max_box_area` | Visual salience proxy. |
| `cheap_track_persistence` | Number of consecutive frames/samples with a candidate track. |
| `cheap_image_motion` | Optical-flow or box-motion proxy if derived without GT labels. |
| `cheap_ego_speed` | Current/past ego speed. |
| `cheap_ego_yaw_rate` | Current/past yaw-rate or steering proxy. |
| `cheap_map_context` | Lane/drivable-area/path prior available at current time. |
| `cheap_source_video` | Scene/source grouping metadata. |

VLM verifier fields, optional and not used in this audit:

| Column | Meaning |
|---|---|
| `vlm_query_text` | Natural-language verifier query. |
| `vlm_clip_path` | Candidate clip path if rendered later. |
| `vlm_label` | Optional verifier output; evaluation-only unless explicitly used for final pseudo-oracle evaluation. |
| `vlm_status` | Runtime/error status. |

Implementation note: the current repository has `garc_eval/adapters/supg_adapter.py` and `garc_eval/adapters/abae_adapter.py`, but no nuScenes adapter. A future adapter should be added under `garc_eval/datasets/` or `garc_eval/adapters/` only after the mini smoke download is explicitly authorized.

## Offline Labels vs Online Signals

Offline evaluation only:

- `sample_annotation`-derived positive labels.
- Future actor positions.
- Future realized ego trajectory when used to define a future corridor.
- Threshold-calibrated event labels.
- Any VLM verifier labels.

Allowed online or cheap proposal signals:

- Current and past timestamps.
- Current and past ego pose, speed, yaw rate, steering, brake, turn signal, and route if they would be available at the decision time.
- Static map and lane context at the current pose.
- Lightweight visual detector/tracker outputs from frames up to the current time.
- Source-video and scene metadata for split grouping, not for memorized ranking.

Conditional signals:

- CAN bus route may be used as a navigation prior only if documented as available at decision time. Realized future ego trajectory from later samples must not be used online.
- Public 3D annotations can be used for offline GT construction, but should not be used to build cheap candidate ranking unless the experiment is explicitly a geometry-oracle ablation.

## Relationship To Current 1000-Clip Pseudo Benchmark

The current `test_vlm` benchmark is VLM-defined and clip-level:

- `source_video`: currently segment id; nuScenes equivalent is `scene.name`, with `stream_id` added for log-level grouping.
- `event_start` / `event_end`: currently clip start/end seconds; nuScenes equivalent is event interval over sample timestamps.
- `conservative_positive`: currently VLM-defined pseudo-oracle; nuScenes equivalent would be geometry-derived offline event label.
- `score_count`, `score_naive`, `score_kinematic`: nuScenes can provide analogous cheap visual and kinematic proxies, but must keep GT geometry separate from cheap proposal signals.

The nuScenes benchmark would be stronger for symbolic-vs-proxy boundary study because it exposes structured geometry and maps. It would not directly replace the current VLM pseudo benchmark: it evaluates geometry-defined traffic interaction, not open-ended visual-risk semantics.

## Minimum Data Download Plan

Do not download full nuScenes initially.

Stage 0, current audit:

- No download.
- Read official docs only.
- Design schema and decision criteria.

Stage 1, if authorized:

- Download/register `v1.0-mini` metadata and the minimal samples required by the devkit.
- Build a sample-level manifest with `scene`, `sample`, `sample_annotation`, `ego_pose`, and `log`.
- Do not run visual models.

Stage 2:

- Add map expansion only if needed for path/corridor construction on mini.
- Add CAN bus expansion only if base 2 Hz ego-pose labels are too coarse for ego-maneuver queries.

Stage 3:

- Materialize the interval table for 2 to 4 scenes.
- Estimate event rates for each query and check whether any query lands in a useful positive-rate range.
- Run adapter smoke only: schema validation, interval non-overlap checks, source-video grouping checks, and leakage checks.

Stage 4:

- If mini is non-degenerate, request explicit authorization before broader trainval download or any proxy/model run.

## Sanity Checks For A Future Adapter

- No event crosses a scene boundary in v1.
- `actor_instance_id` is prefixed with `scene_token` to avoid false cross-scene continuity.
- Event labels are unchanged by source-video split metadata.
- Offline label fields are not present in candidate-ranking inputs.
- Event count should be stable under small timestamp jitter and should not explode when the merge gap increases.
- For each event query, report positive intervals per scene, source concentration, event duration distribution, and actor category distribution.
- Learned proxies, if added later, must use source-video/log grouped train/validation/test splits.

## Support Matrix

| Capability | Assessment | Notes |
|---|---|---|
| Video-level query retrieval | Partial | Scenes are short 20s clips, but log-level stream grouping can support retrieval over concatenated streams. |
| Query-conditioned candidate coverage | Good | Queries can be geometry-defined and compared against cheap visual/kinematic proposals. |
| Temporal interval evaluation | Good | 2 Hz sample annotations support interval labels; short/fast interactions may be coarse. |
| Cross-video generalization | Good if split by scene/log | Must split by `source_video` or `log_token`, not random samples. |
| Calibrated symbolic rule comparison | Good | Maps, ego pose, actor boxes, and CAN bus enable explicit rule baselines. |
| Real semantic risk retrieval | Weak | Geometry events do not prove human-perceived risk or query semantics without separate audit. |

## Risks And Limitations

- 2 Hz actor annotations are coarse for short interactions.
- Scene length is only 20s, so long-horizon stream experiments require careful log-level concatenation.
- Instance identities do not persist across scenes.
- CAN bus is useful but officially experimental.
- Geometry-derived labels can include actors not visible or hard to verify visually.
- Query thresholds may dominate event rates; mini calibration is mandatory before broader claims.
- A geometry benchmark may over-favor symbolic rules compared with visual-language proxies; that is acceptable for a symbolic-vs-proxy boundary study but must be stated.

## Final Decision

`PARTIAL_GO`

nuScenes is worth a controlled mini adapter smoke test for a geometry-grounded event-AQP benchmark. It should not yet be promoted to a full external benchmark until `v1.0-mini` confirms non-degenerate event rates, stable query thresholds, and manageable ambiguity for at least two event types.
