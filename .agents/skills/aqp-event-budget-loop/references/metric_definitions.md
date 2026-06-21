# Metric Definitions

Use these definitions for pseudo-event budget experiments.

Let `N` be the number of candidate clips, `B` the simulated VLM call budget, `S_B` the first `B` selected unique clips, `P` the set of conservative VLM positive clips, and `E` the set of pseudo-events created by merging positive clips within the configured source-video/time gap.

## Clip Recall

`clip_recall(B) = |S_B intersect P| / |P|`

If `|P| = 0`, report the metric as undefined and do not interpret it as success.

## Pseudo-Event Recall

An event is found when at least one member positive clip of the event appears in `S_B`.

`pseudo_event_recall(B) = found_events(B) / |E|`

If `|E| = 0`, report the metric as undefined and do not interpret it as success.

## Unique Events Found

`unique_events_found(B) = count({e in E : members(e) intersect S_B is non-empty})`

## Redundant Call Rate

A selected positive clip is redundant if its event was already found by an earlier selected clip. A selected negative clip is not an event duplicate but is still an unproductive call; report it separately when useful.

`redundant_call_rate(B) = redundant_positive_calls(B) / B`

## Calls Per New Event

`calls_per_new_event(B) = B / max(unique_events_found(B), 1)`

Also report undefined or `inf` when no event is found, depending on the plotting/table convention.

## Event Discovery Curve

For a complete ordered selection list, plot cumulative `unique_events_found` or `pseudo_event_recall` against calls. Random baselines must show mean and 95% interval across seeds.

## Calls To Target Recall

`calls_to_first_event` is the first rank where `unique_events_found >= 1`.

`calls_to_50pct_event_recall` is the first rank where `pseudo_event_recall >= 0.5`.

`calls_to_80pct_event_recall` is the first rank where `pseudo_event_recall >= 0.8`.

If the target is never reached, report `NA`.

## Source Video Coverage

`found_event_source_video_coverage(B) = number of distinct source videos among found pseudo-events / number of distinct source videos among all pseudo-events`

Use this to diagnose whether gains come from event-aware scheduling or source-video concentration.
