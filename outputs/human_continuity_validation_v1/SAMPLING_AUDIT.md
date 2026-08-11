# Sampling Audit

Protocol: `06deda4503981179bdd2bc9157f94f80c104dcc7fffb5e866da4fd10325716ac`. Seed: `20260811`.

Primary is source-balanced 13/13/14 across DALI/HANGZHOU/WUHAN, with predeclared per-video targets favoring C0/C1 disagreement, then C1/K3 disagreement, then agreement controls. Shortfalls are deterministically filled by the same predeclared priority. Reserve is selected from the remaining population only and remains locked.

Sampling uses only video/unit/time metadata and hidden method prediction patterns. It does not use any human preview or label. The manifests retain video×pattern population counts, sample counts, inclusion probability, and inverse-probability descriptive analysis weight. Temporal diversity tries a frozen `120.0`-second separation within video, then deterministically relaxes it only to meet a required quota.
