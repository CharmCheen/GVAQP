# VLM-defined held-out reference recovery and corrected EVENT_ENUMERATE v2 gate

## Exact decision

`VLM_REFERENCE_INCOMPLETE`

`REFERENCE_TYPE = VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`; `HUMAN_GT = false`;
`REAL_WORLD_SEMANTIC_CLAIM = false`.

`test.mov` passes independence under the user-provided non-overlap and non-use
premises, supported by different byte hashes, media properties, and sampled
perceptual fingerprints. The requested exhaustive decoded-frame/offset and
audio-fingerprint comparison was not completed, so this is not claimed as a
standalone empirical proof. However, no exhaustive `enter_ego_path` VLM
reference exists for its 43.043333-second timeline. The recovered 399-anchor,
51-event Qwen3-VL reference belongs to the different 3987-second
`realcartest` video. The sole claimed slice also fails content correspondence.
The exhaustive 1775-row artifact naming `test.mov` is a YOLOv8x vehicle-count
table, not a VLM VEPC annotation.

Therefore the reference was not frozen, no processor/model audit was started,
no physical plan was constructed, and physical calls equal zero. Quality and
cost metrics are `NOT_MEASURED`; VERA viability remains unresolved.

Independent review: `PASS_WITH_CAVEATS` on the scientific decision and stop
logic. Its caveats concern assumption-supported independence, the contradiction
between the supplied slice statement and current bytes, and incomplete
computational independence checks.

Exact next task: supply or identify exhaustive prompt-conditioned
`enter_ego_path` VLM observations whose recorded frame inputs map to
`try_or_no/test.mov` across its complete timeline. Alternatively, authorize a
new independent reference-generation pass distinct from EVENT_ENUMERATE;
that would be new oracle inference and must be sealed before operator sample
selection.
