# Post-amendment independent adversarial review

Decision: `BLOCKED_INTERNAL_INCONSISTENCY`.

The amendment occurred before any toy or physical policy result was visible,
D2-T uses mathematical support rather than physical timings, D2-P remains
blocked, and no held-out runner was executed. The dependency split itself is
valid.

The frozen D3/D4 assets do not uniquely specify a non-clairvoyant M1:

1. `ratio_draw` is used by the SCAN law but is absent from the ordered RNG
   schedule. Inserting it anywhere changes downstream fixed-seed assignments.
2. grouping is scheduled after all witnesses are generated and uses latent
   event identity, conflicting with incremental SCAN visibility. An online
   grouping transition and its draw order are unspecified.
3. lazy action-ledger cost draws make potential action costs depend on the
   policy trajectory. No action-identity coupling across paired methods is
   frozen.
4. D4 requires visible-history conditional expectation, but D3 specifies no
   belief state, observation likelihood, posterior sampler, seed visibility,
   or exact safe-action domain for M1.

Cloning the realized Episode for M1 would leak future latent truth and turn M1
into the separately defined C0 clairvoyant ceiling. The one evidence-supported
direct repair was to make that evaluator fail closed. No alternate generator
or posterior was chosen post hoc.

Required resolution is a result-blind D3/D4 reissue with domain-separated draws
for every variable (including ratio), action-identity potential costs shared
across methods, incremental grouping, explicit seed/parameter visibility, and
an explicit visible-history conditional kernel. All dependencies must then be
rehashed and independently reviewed before development smoke.

