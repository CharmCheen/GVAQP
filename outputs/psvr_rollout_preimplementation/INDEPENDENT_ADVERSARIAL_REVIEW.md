# Independent adversarial review

Status: `COMPLETE_ONE_REVIEW_ONE_DIRECT_REPAIR`; residual terminal state: `BLOCKED_D2_NUMERIC_BINDING`.

## Review method

A separate reviewer inspected the completed D1--D4 documents, machine-readable specifications, policy helper, tests, manifest, and completion audit against the full preimplementation request. The reviewer was instructed to seek—not endorse—utility double counting, AUC misuse, F1/surrogate confusion, undefined policy states, unsafe fallback, dirty commits, quantile composition, future/latent leakage, split overlap, post-hoc freedom, named-scenario cherry-picking, rollout-theorem overclaim, and accidental M0 dependency.

## Blocking findings from the independent first pass

1. D3 originally gave ranges without a unique seed-to-episode construction algorithm; permissive transition objects allowed conforming implementations to disagree.
2. D4's acceptance list did not separately require a win over Ratio-PSVR even though the scientific question did.
3. D2 labeled the sum of two marginal 0.9 operational bounds as `ALPHA_CONFIRM=0.1`; this chance interpretation was unsupported.
4. Metric edge cases, regime aggregation, continuous-positive-neighborhood size/connectivity, and MC tolerance retained post-hoc freedom.
5. Completion checks were pending, and the policy helper returned only witness ID even though CONFIRM identity is `(hypothesis,witness)`; recursive latent fields and invalid numeric inputs were not all rejected.

The reviewer agreed that the missing full-obligation pre-action SCAN bound is a real D2 numeric blocker. No evidence was found of utility double counting, F1/surrogate conflation, unsafe SAFE_HARBOR behavior, dirty durable state, actual seed overlap, named-scenario promotion, M0 dependency, or rollout-theorem overclaim.

## Single direct repair

- Added `TOY_CONSTRUCTION_SPEC.json`: frozen SplitMix64 algorithm and conformance fixture, binary64 convention, exact seed indexing, ordered draw schedule, split-specific laws and weights, M/geometry/horizon, absolute and variable costs, event/emission/grouping/suppression/CONFIRM kernels, identifiers, visibility projection, and canonicalization. Tightened schema objects and bound construction into the YAML, D4, and manifest hashes.
- Added explicit M1 > B4 and M1 > maximum frozen simple comparator gates and acceptance conditions. Froze every baseline action rule.
- Set `ALPHA_CONFIRM=null`, recorded it as blocking, and retained 27.390509267 seconds only as the exact legacy operational reserve—not a complete-action 0.9 quantile.
- Froze exact primary/F1/TTFC/matching formulas, empty/censoring rules, paired macro/regime aggregation, theoretical heatmap bins, minimum cell count, three-bin neighborhood rule, numerical tolerance, independent MC stream keys, cap, and numerical-block branch.
- Changed CONFIRM output identity to `(hypothesis_id,witness_id)`, added recursive forbidden-field checks and finite/nonnegative input checks, and added focused tests.
- Corrected “disjoint distributions” to “disjoint seed universes”; split-specific parameter distributions are separately frozen and may intentionally have overlapping support.
- A narrow recheck found the named scenarios were still qualitative. The same repair cycle added `TOY_NAMED_SCENARIOS.json` with all ten exact diagnostic fixtures and bound its SHA-256 through the construction spec, parameter YAML, D4, and manifest. Every fixture has `primary_inference=false`.

## Residual defects and decision

No repaired internal contradiction is knowingly hidden. The remaining blockers are external numeric evidence gaps already exposed in D2: no directly calibrated complete pre-action SCAN obligation or `ALPHA_SCAN`, no directly calibrated chance level for complete CONFIRM, and no certified physical minimum action duration. Logical properness additionally follows from a finite decreasing rank, so the last item is a requested numeric field gap rather than the dominant executability blocker.

The review therefore does **not** clear the package for toy policy comparison. It clears the repaired design package only for the declared terminal status `BLOCKED_D2_NUMERIC_BINDING`. Any later D2 calibration must trigger a new revision, full revalidation, and complete hash rebinding before H-ROLLOUT1A execution.

Final narrow reviewer disposition: `CLEAR_FOR_DECLARED_D2_BLOCK`. The reviewer independently reran the static validator (`33/33`, zero failures), focused tests (`9 passed`), and hash audit (no mismatch), and found no remaining internal contradiction in the repaired design.
