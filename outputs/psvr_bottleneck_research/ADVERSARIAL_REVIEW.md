# Independent adversarial review

The independent reviewer supports `H-STAGE1 = REJECT` and `PSVR_TWO_VIDEO_SEARCH = NO_GO`, with
three qualifications.

First, H-STAGE1 has 48/48 complete physical cells, 24/24 F0–C10 behavioral endpoint equivalence,
and zero safety/durability failures. However, the preregistered exact-repeat signature condition is
14/16, not PASS. The two divergent cells differ only by one tail VERIFY under physical latency;
16/16 final semantic event signatures agree. This blocks positive acceptance but does not weaken
the conservative V1 null.

Second, V1 is heterogeneous. V1_Q1 positive candidates are created but immediately discarded
before frontier entry. V1_Q2 has positive candidates that enter and survive the frontier but never
receive VERIFY. The authoritative mechanism evidence is the actual lifecycle table, not the legacy
“every three scans” survival diagnostic, which is inapplicable to a dynamic controller.

Third, the same cycle used two validity repairs: refreshing 24-hour-expired physical profiles and
then restoring historical fixed-control action counts after the refresh changed computed counts.
Both were preregistered, result-blind, and retained their invalid traces, but the pair is a procedural
deviation from the one-repair discipline. It lowers evidence level and precludes acceptance.

No alternative explanation reverses the outcome: only V0_Q2 wins; V1 is 0/12; macro AUC gain is
5.75%, F1 gain is 0.0192, TTFC worsens, and only one additional event is recovered. This is not a
near miss and triggers neither revision nor ablation.
