# Materializer Contract

## Unified Interface

`materialize(units, observations, config) -> list[MaterializedEvent]` consumes public `AtomicUnit` records and typed `OracleObservation` records. GT is never an argument.

- `M0SimpleRunMaterializer`: fixed-gap positive-anchor merge; ordinary negative core evidence remains soft; typed `DISTINCT` splits; typed `SAME` overrides the explicit unsafe hard-gap baseline.
- `K3AdapterMaterializer`: calls the actual Stage 0.7 `construct_k_segments`; accepts core/explore binary outcomes, ignores relation observations with an explicit counter, and is frozen to repository duration parameters.

## Posterior Contract

`posterior_interface.py` defines, but does not compute:

- event interval posterior;
- same-event marginal;
- event-count posterior;
- MAP event partition;
- boundary marginals.

No HSMM output is fabricated.

## Sufficiency Assessment

Current K3 logs are sufficient to replay a deterministic binary-anchor partition. They are insufficient for a posterior latent-event materializer because they lack:

1. typed `SAME` / `DISTINCT` / `AMBIGUOUS` relation outcomes;
2. observation confidence, abstention likelihood and source provenance;
3. action-specific likelihood/error models and costs;
4. boundary evidence distinct from existence evidence;
5. actor/schema identity and unit multiplicity;
6. an explicit distinction between normal negative evidence and a semantic separator.

Therefore K3 observations cannot identify event count, split/merge identity or same-event marginals without additional assumptions.
