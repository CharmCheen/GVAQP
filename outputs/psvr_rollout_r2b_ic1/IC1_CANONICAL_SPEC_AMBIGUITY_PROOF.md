# Canonical-spec ambiguity proof — generative error transitions

## Question tested

Can BASE → A1 → A2 → A3, together with the frozen R2 kernel, uniquely map a
sampled planner world and an A2 error key to the next **generative** planner
state for all six error mechanisms?

## Sources inspected

| Artifact | SHA-256 | Relevant content |
|---|---|---|
| BASE approximation/error model | `f69725a136bd17ff071d36b77824aba302e71b56a7647f4107e01a5679b1b94d` | names the six mechanisms and probability/duration bounds |
| A1 precision amendment | `62b6a2e508b59ab06f06ba56cb7e646026a39a60442b18e3dc2965773bb73f03` | defines signs and probability/duration transforms |
| A2 target canonicalization | `f271c4bb458e37913f98be35152477f9f05ad4eb51f6615475f7f4669f41563d` | defines target identities and draw indices |
| A3 chain integrity | `3e6f27e801a816685332764e36e73951baed71c1dd6102ea7dca88d2fe0aa289` | binds hashes; adds no transition semantics |
| implementation canonical snapshot | `9fb9edc80962a2c468eb6703fdf223bb5c53c18cbfb4086784f830d544c2fc52` | lists error axes/CRN but no transition kernel |
| implementation resolution audit | `554fbc20e0a1e8ac1339f6a401767b214b6db6a9bcc0fe7054089c3f0c79657f` | says `RESOLVED_UNIQUELY`, but does not enumerate these missing mappings |

The complete source search found no later A3 amendment or canonical-snapshot
field defining them.

## Counterexample 1: a probability has no unique trajectory realization

For an actual R2 scan in `world-007`, candidate
`(hypothesis_id=h00_0, witness_id=w00_0, score_bin=3)` is visible. The exact
visible-history posterior assigns its CONFIRM-positive event probability
`p = 1/3`. For trajectory 2, the A2 canonical key is:

```text
H1B_ERROR|development-0000|1|confirm_positive_probability|independent_variance|2|CONFIRM|h00_0|w00_0|0
```

Its SHA-256 digest is:

```text
c733a5c12cfe6fbdac3371587355a0251b71a4855bc5e7957a164a0c034e7ec1
```

The required first-bit sign is `+1`; at magnitude `.05`, the A1 probability
transform therefore gives `p' = 0.3833333333333333`.

Both of the following are deterministic, keyed probability realizations that
use that exact full A2 key and preserve its mandated sign:

| Realization | Uniform value | Outcome for `p'` |
|---|---:|---|
| bytes 1–8 of the digest, big-endian divided by `2^64` | `0.2017479643677111` | positive |
| full 256-bit digest divided by `2^256` | `0.7781318279858114` | negative |

Neither BASE, A1, A2, nor A3 selects a uniform mapping, a threshold rule, or
any other probability-to-trajectory rule. The two outcomes yield different
future frontiers, commits, values, LCBs, and potentially selected actions.
This is not an implementation-format difference.

## Counterexample 2: grouping has no specified state transition

In `world-000`, scanning `r00` exposes two candidates with the same frozen
`hypothesis_id`, `h00_0`: `w00_0` and `w00_1`. A2 assigns a canonical `GROUP`
target and pair rank, while A1 says a grouping transition is "a probability
that two candidates with equal frozen hypothesis_id are grouped." Neither
artifact defines either resulting state:

- on a successful grouping draw, whether the pair remains represented by two
  witnesses, one canonical witness, or an aggregate confirmation action; or
- on a failed grouping draw, whether the pair is split into distinct model
  hypotheses and, if so, the required deterministic identifiers and token
  relationship.

These alternatives directly affect legal CONFIRM actions, duplicate handling,
continuation policy, and D1 reward. No R2 transition can supply the missing
rule because R2 exposes only the already-realized true grouping.

## Additional unresolved mapping

For retention, positivity, novelty, and materialization, A1 defines how to
perturb a supplied probability but never defines the baseline probability in a
sampled deterministic R2 world. Plausible candidates—latent indicator,
visible-history posterior predictive probability, or a model-calibrated
probability—are not equivalent and are not selected by the frozen chain.

## Conclusion

The chain uniquely defines target labels and a probability transform, but not
a complete generative transition kernel. A generative implementation would
have to add scientifically material choices. Under the task's source-of-truth
rule, this establishes `BLOCKED_CANONICAL_SPEC_AMBIGUITY` rather than an
ordinary implementation blocker.

## Required resolution

A new result-blind, hash-bound clarification must specify, for each mechanism:

1. the baseline probability/quantity conditional on a sampled planner world;
2. the exact deterministic keyed probability realization convention;
3. the resulting model state/action/token transition; and
4. the common-JOINT behavior for every error form, including
   state-dependent calibration.

It must preserve the frozen grids, metrics, seeds, Gate, and result blindness.
