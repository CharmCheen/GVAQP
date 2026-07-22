# Pseudocode

```text
VERA(V, q, profiles, targets):
  edges <- enumerate legal EVENT_ENUMERATE and DENSE_UNIT cores
  plan  <- risk_constrained_shortest_path(edges, targets)
  assert plan cores form one disjoint cover

  fragments <- []
  for edge in plan chronological order:
    commit atomic request(edge, hashes, frame schedule)
    result <- execute edge operator
    atomically persist raw response, timings and resource ledger
    if parse-valid relation fragment:
      fragments.append(fragment)
    else:
      execute preregistered dense fallback for edge core

  owned <- retain fragment events whose canonical point is in edge core
  E_hat <- deterministic_overlap_reconcile(owned, all fragments)
  return E_hat with lineage and complete cost vector
```

The sprint pilot fixes the uniform plan before execution; the general DP is
tested in simulation because no held-out data exists to calibrate its operator
risk profiles.

