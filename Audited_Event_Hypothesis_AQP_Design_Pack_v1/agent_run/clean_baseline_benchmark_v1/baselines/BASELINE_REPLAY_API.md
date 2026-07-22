# Baseline Acquisition Replay API

Every valid baseline run stores an ordered `action_trace.csv` and the benchmark stores one immutable, full physical cache in `oracle/oracle_presence_observations.csv`. Logical replay reads labels only for unit IDs present in the selected trace. It never exposes unqueried labels to a planner and performs no new VLM calls.

```bash
PACK=Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1
TRACE="$PACK/baselines/controlled_track/B1_top_proxy/top_proxy_controlled_bridge_safe/seed_000/budget_20/action_trace.csv"

python "$PACK/scripts/replay_baseline_acquisition.py" \
  --trace "$TRACE" \
  --oracle-observations "$PACK/oracle/oracle_presence_observations.csv" \
  --materializer original_k3 \
  --output-dir /tmp/b1_original_k3_replay

python "$PACK/scripts/replay_baseline_acquisition.py" \
  --trace "$TRACE" \
  --oracle-observations "$PACK/oracle/oracle_presence_observations.csv" \
  --materializer k3_bridge_safe \
  --output-dir /tmp/b1_bridge_safe_replay
```

Inputs are the trace, frozen observations, frozen unit/reference tables, materializer name, and evaluator config. Outputs are `event_segments.csv`, `event_matches.csv`, `metrics.csv`, and `replay_manifest.json`. A materializer-only change can therefore be evaluated without rerunning acquisition or the VLM.

