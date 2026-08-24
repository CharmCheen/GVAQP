# B0 action and information contract

## Actions

| Action | Input | Newly visible output | Legality | Cost |
|---|---|---|---|---|
| `SCAN(region)` | public query and region | 0-N fallible candidates with proxy scores | region exists and not previously scanned | frozen scan cost |
| `VERIFY(candidate)` | previously exposed candidate | local verified relations or explicit failure | candidate exposed and not verified | frozen candidate cost |
| `DIRECT_VERIFY(region)` | public query and region | local verified relations or explicit failure | region exists and not directly verified | frozen direct cost |
| `STOP` | public state | none | always | zero |

There is no fallback candidate. DirectVerify is not implemented through a
hidden candidate table. SCAN and DirectVerify may both target a region because
they buy different information.

## Policy-visible state

The policy sees query ID, elapsed/deadline, public regions, scanned and directly
verified region IDs, exposed candidates and scores, verified candidate IDs,
and committed events built from observed local relations.

It never sees reference event count, reference event IDs, future candidates,
unobserved verifier outcomes, oracle regret, or hindsight best actions.

## Clock and evaluator

Every completed action debits the same elapsed clock. An action that would
cross the deadline is logged as rejected and causes no exposure, verification,
materialization, or elapsed-time mutation. All policies use the same online
materializer and anytime/terminal evaluator. Identical action/evidence traces
must score exactly equally.

## Materialization

Only returned local relations participate. Relations with identical sorted
locally observed participant keys and gap no larger than the frozen merge gap
are merged. No global reference event ID is available to the materializer.
