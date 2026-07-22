# H-SCAN1A mechanism analysis

## Decision

`H-SCAN1A=ACCEPT_STRUCTURAL_SIGNAL` (Branch S-A). D1 and D2 recovered one event in every formal repeat at both deadlines; D0 and D3 recovered none. D2 retained the full method's endpoint quality and improved mean AnytimeAUC and median TTFC while removing the proxy group.

## Time chains

D1 first touches a reference-positive unit and observes its proxy during the first scan batch (~0.49 s median). Its eventual unit 317 reaches the visible frontier after three higher-scored negative VERIFY completions (~68.0–68.6 s), is physically verified fourth, and is durably confirmed at ~89.0–89.5 s median as `vlm_event_0022`.

D2 also touches a positive unit in its first scan batch. Its eventual unit 246 reaches the frontier at ~69.9 s, is verified fourth, and is confirmed at ~86.8–86.9 s median as `vlm_event_0017`. Thus D2 does not reproduce D1's event identity; it preserves quality through a different structural search path.

D3 touches positive reference cells physically, but its proxy-only ranking never promotes a reference-positive scanned unit to the top candidate frontier. Its five VERIFY targets are negative. Therefore failure occurs between relevant proxy exposure and candidate creation, not because of missing scan or VERIFY budget.

## Coverage and exposure

- D0: 10 positive cells touched; max gap 20 s; no useful candidate.
- D1: 17 positive cells touched; max gap 40 s; median global-gap integral about 0.0121–0.0126.
- D2: 17 positive cells touched; max gap 40 s; median global-gap integral about 0.0112–0.0114.
- D3: 9 positive cells touched; max gap 1725 s; median global-gap integral about 0.273.

All methods use 29 scan batches. D3's severe gap and lower positive exposure arise from its frozen proxy-only ordering and zero-signal tie behavior, not fewer actions.

## Tie-break dependence

D2's winning unit 246 is selected in batch `[224,235,246,257]`; these cells have equal structural priority. Unit 246 and 257 are both included, so their within-batch order does not determine exposure. However, the ascending-unit tie-break determines which equal-priority cells cross the four-slot batch cutoff. The structural claim is therefore conditional on the frozen hierarchy and tie-break. H-SCAN1B must preserve this tie-break and include a diagnostic alternative-tie replay after execution.

## Cost and stability

There are no deadline misses, failures, replays, future accesses, or visibility violations. Scan prefixes and event sets are consistent in all eight method/deadline cells. D1 exact action traces vary only because one repeat at each deadline safely stops after four rather than five VERIFY calls; the positive event is already the fourth target. D2 and D3 exact traces are stable.

Scheduler RPC overhead is unavailable in the inherited runner and is explicitly not reported as zero. GPU, physical calls, decode counts, unused deadline, and checkpoint commit durations are included in the metric tables.
