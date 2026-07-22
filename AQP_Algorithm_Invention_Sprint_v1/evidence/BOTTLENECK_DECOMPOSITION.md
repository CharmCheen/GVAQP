# Bottleneck decomposition

## Strongest supported conclusion

The strict evidence rejects another unit-ranking or Boolean-pruning mechanism.
The remaining high-leverage uncertainty is whether one physical invocation can
return a *set of event objects* over a longer interval cheaply and accurately
enough to amortize semantic inference. This is a new operator question, not an
inference from the existing unit oracle.

## Observed evidence

| Layer | Direct evidence | Headroom status |
|---|---|---|
| Search/proposal | H1 legal universe covers 20/26; public blocked-CV AUROC 0.548282 | Large oracle-ordering headroom exists (AUC 0.664458), but the runnable public signal is weak |
| Semantic operator | Existing strict primitive is one 10-second presence result per call; median physical generation is about 15.35 s | Set-valued interval enumeration is unmeasured and is the dominant uncertainty |
| Materialization | K3-safe family-macro AUC 0.317644; exact legal partition ceiling 0.318514 | Only +0.000870 AUC, so partition optimization is not the dominant opportunity |
| Audit/certification | DARE needs 311 calls with best public rank; risk-limiting interval audit needs at least 350 single-placement or 550 all-placement calls for quality-valid cells | Frozen distribution-free/unit-audit route has no feasible region |

## Cost dimensions that must remain separate

| Cost | Definition in this sprint | Existing evidence |
|---|---|---|
| Logical call cost | Number of semantic-operator invocations independent of caching | Dense unit presence is 347 calls |
| Physical GPU cost | Synchronized model generation GPU time plus preprocessing/decode where reported separately | Strict 10-second Qwen3-VL generation mean 15.41 s/call; CLIP and X-CLIP ledgers are separate operators |
| End-to-end latency | Model load + video decode/preprocess + generation + parsing/reconciliation | Must be measured for the selected physical operator |
| Cold-index cost | One-time model load and any video-wide reusable index build | Charged in cold execution, never silently amortized |
| Warm-query cost | Query-specific work after a compatible index/cache exists | Reported only when the cache key includes video, model, sampling, and operator contract |
| Amortized workload cost | `(cold build + sum query costs)/number of compatible queries` | A hypothesis only until a workload and cache reuse contract are defined |

## Competing hypotheses

- **H-enum:** A variable-resolution event-enumeration operator can expose
  multiple distinct events per invocation; a global relation-cover plan can
  beat dense execution in GPU seconds while meeting event recall/F1 targets.
- **H-token:** Longer intervals merely move cost into frames/tokens and lose
  brief events; their physical runtime or error rate erases logical-call
  savings.
- **H-search:** Enumeration works locally, but without a strong public search
  signal uniform coverage dominates cost, reducing the method to ordinary
  retrieve-then-ground or longer clips.
- **H-amortize:** The only defensible advantage is warm multi-query reuse; the
  single-query cold path has no gain.

## Decision-critical experiment

First compute evaluator-backed ceilings and sensitivity/cost break-even regions
for a typed set-valued operator. A physical pilot is justified only if the
region includes non-perfect sensitivity and conservative interval-cost scaling.
The physical result must reject H-token by directly measuring event output,
frames/tokens, GPU time, and end-to-end latency. Failure to reach the frozen
quality/cost gate closes the selected mechanism without another prompt sweep.

