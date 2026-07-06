# Oracle Adapter Specification

```python
class OracleAdapter:
    def __init__(self, grid, ref, segment_id):
        # grid: atomic units with is_positive and bin_idx
        # ref: full-VLM reference events (hidden from method)

    def query_unit(self, bin_idx: int) -> str:
        '''Returns 'positive' or 'negative' for the requested unit.
        Increments oracle_call_count.'''

    def query_interval(self, t_start: float, t_end: float) -> str:
        '''Returns 'positive' if any unit in [t_start, t_end] is positive, else 'negative'.
        Counts as one oracle call.'''
```

## Rules

- Each `query_*` call increments `oracle_call_count`.
- The method cannot access `grid['is_positive']` or `ref` directly.
- `event_id` is never returned to the method.
- The final evaluator may read `ref` only after the method returns.
