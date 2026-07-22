# Benchmark v2 Oracle Build Report

- Status: `COMPLETE`
- Units: 347
- Reused raw responses: 346
- New raw responses: 1
- Physical VLM calls: 1
- Forced requery: unit 346, `[3457.93,3462.93]`
- Old unit-346 label: `negative`
- New unit-346 label: `negative`
- Prompt SHA256: `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`
- Model manifest hash: `921540a4c33c8f8608f77c34af99741ff0828e79e66cd79af13bdc702b02f0ea`
- Processor hash: `d511a3af5ed95c352b5a05397ddf9f9f4a4c89c1045555d5e8e09fe9b869749d`
- Video-processor hash: `b26c36218bdc3022636f68556ed9b5c7a2553851d8f26c90472205f1ad87358c`
- Generation-config hash: `1e736848fe36a1749e2be336faa46cbf6403d55861c9945b9e677df2b24031db`
- Parser hash: `2b0c34cb3d759aaab5d0ca3801c2c2b78bfb208f13d9449e6c9ab07b0c2bb30e`
- Sampling-code hash: `a64dd0acdbf1913662073d303ea5818999932defbc3e04061a3c2fb0353024b8`

The unit-346 raw response was atomically saved before parsing.  Every raw cache
entry is copied/content-bound inside this package and keyed by video, unit
interval, frame indices/content, model/processor/generation/prompt/parser, and
sampling code.  Method budgets are not charged here; future logical queries are
charged through `OracleAccessor` even when these files are cache-backed.

## Independent-review correction

The current hashes stamped on reused units are reconstructed current configuration identities, not preserved generation-time hashes. Therefore units 0–345 fail the strict historical configuration-equivalence proof and the attempted cache is not freeze-eligible without fresh inference or a protocol amendment.
