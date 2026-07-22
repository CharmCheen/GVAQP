# A4 baseline transition kernels

Each planner rollout uses a posterior-sampled R2 root world as its latent
planner state, never the actual execution world's future. For a proposed
action and current simulated branch state, `P0` is derived from that root
world's corresponding R2 transition: candidate existence/yield, score,
duration, confirm positivity, event-token novelty, grouping relation, and
materialization are all conditionally degenerate before A2 transformation.

Binary probabilities are the latent indicator (`0` or `1`) and retain A1's
required `.01,.99` clipping when A2 is applied. Durations use the root-world
action duration and its frozen R2 support. Grouping is categorical over
`CORRECT`, `UNDER_MERGE`, and `OVER_MERGE`, with degenerate baseline `CORRECT`.
The approximate model may use only its sampled root world, current simulated
branch state, and visible pre-action state; it may not read actual execution
future state or evaluator randomness.
