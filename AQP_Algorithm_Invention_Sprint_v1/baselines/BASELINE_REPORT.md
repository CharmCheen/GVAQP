# Strengthened baseline evaluation

Two comparisons are intentionally separated. Native ARC/SUPG/ABae/MAP/CLIP rows retain their frozen 10-second `UNIT_PRESENCE` query object. The shared-operator experiment instead reorders the exact same 70 physical `EVENT_ENUMERATE` outputs, making physical costs and relation composition identical at full coverage.

VERA chronological has same-cost event-F1 AUC `0.005540`, full event F1 `0.052632`, and full GPU cost `1566.323` seconds. The best deployable shared-operator label is `ALL_DEPLOYABLE_TIED` at `0.005540`; tied methods are `ABae_plus_EVENT_ENUMERATE|ARC_plus_EVENT_ENUMERATE|CLIP_RTG_plus_EVENT_ENUMERATE|MAP_M1_plus_EVENT_ENUMERATE|SUPG_plus_EVENT_ENUMERATE|VERA_chronological|public_proxy_plus_EVENT_ENUMERATE|uniform_random_plus_EVENT_ENUMERATE`. The fallback stage is appended identically after all 70 enumeration windows. This ordering result is diagnostic: VERA's claimed novelty is the variable-resolution relation-cover operator plan, not a new relevance ranker.

Native frozen AUCs remain: ARC `0.389659`, MAP/M1 `0.388056`, CLIP retrieve-then-ground `0.538949`, SUPG-adapted `0.278128`, and ABae-adapted `0.303198`. These AUCs are not silently equated with the shared-operator AUC; both use the same six dense-equivalent budget points, but the physical query objects differ.

The evaluator-oracle order is explicitly nondeployable. Physical pilot gate: `FAIL`.
