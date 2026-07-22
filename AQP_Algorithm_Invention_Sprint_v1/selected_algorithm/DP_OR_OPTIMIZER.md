# DP / optimizer

The timeline positions are vertices in an acyclic graph. Each legal
enumeration or dense edge advances from core start `i` to core end `j` and has
predicted cost `c_a` and nonnegative risk `r_a`. Risk is rounded upward to a
fixed quantum. `D[j,k]` stores the cheapest prefix cover ending at `j` with
rounded risk at most `k`.

```text
D[0,0] = 0
D[j,k] = min_(a:i->j) D[i,k-ceil(r_a/q)] + c_a
```

Parents reconstruct the plan. Tie-breaking is cost, risk, physical calls,
maximum input span and lexical edge sequence. Implementation:
`garc_eval/aqp_invention_v1/planner.py`.

Complexity is `O(AK)` time and `O(NK)` state for `A` edges and integer risk
budget `K`. If batch sharing or overlap interactions invalidate additive edge
cost/risk, the state is insufficient and the exactness claim does not apply.

