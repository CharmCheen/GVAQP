# Strict v2 public-proxy retention audit

Status: `PASS_PUBLIC_ONLY_CONTENT_EXACT_COPY`

The strict benchmark retains the previously clean-generated unit grid and
cheap public proxy precompute.  This is deliberately distinct from oracle raw
responses: none of these files contains oracle labels, reference events,
selections, traces, segments, matches, metrics, rankings, or aggregates.

The retained producer is
`outputs/video_feature_precompute_v1/scripts/precompute_video_features.py`
(SHA256
`0a878d23c5f0500160e098a517142e38ab67f83c0fff25a1c1667094a73ca69e`).
Its source video SHA256 is
`bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`.
The original run reported 693 valid five-second feature rows and 347
center-ten anchor rows.

The strict copy preserves all seven source artifacts byte for byte:

| File | SHA256 |
|---|---|
| `center10_anchor_grid.csv` | `8d652d0aaa5659466af6b0c8baf755e384e70b28e43081de69893460a9bfc716` |
| `center10_proxy_features.csv` | `b84b34b83de5e9f6263cd12e63f95c0b8c79c59e85e7671d5de50b0c933dcdec` |
| `coarse_5s_clip_grid.csv` | `00ccd085caa3acc6cf9514f8af65c8658d901eb532484df3b8d80243f1cc20f5` |
| `precompute_summary.csv` | `b15fcff57daf41729ed2a17a762f51156ad450745f666aad547551cea7e7ee39` |
| `proxy_features_5s.csv` | `9fb6c4d60e6bd3b563433290aca3967c8afc72e70acb1aac089c7e0fa1b0d224` |
| `sanity_checks.csv` | `3b796618c401dfcdc2fb8fd89ae0be0a2247c5ae631c7236ade7928717cb567f` |
| `video_metadata.json` | `2593cd5ac4532197f4cc101175e2ca84a2c814af5e39f05cf33fc3e8711f5cac` |

The authoritative MP4-format duration is `3462.930499` seconds.  The grid has
347 units and intentionally ends with the clipped interval
`[3457.930, 3462.930]`.  Strict oracle inputs were independently rebuilt and
freshly queried; this public-proxy retention grants no permission to reuse any
legacy oracle response or downstream result.
