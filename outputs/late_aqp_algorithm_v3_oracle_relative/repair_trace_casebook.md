# Repair Trace Casebook
This casebook examines Ours-full vs B7 at the case level for budgets 10, 20, 40, 80.
**Important**: The current selection log does not record whether a selected bin came from initial envelope discovery, audit sampling, or repair expansion. Therefore causality is inferred, not proven. Unknown fields are marked `unknown_not_logged`.

## Budget = 10
### Long-interval events
- Ours hits but B7 misses: []
- Both hit: ['realcartest_event_0028', 'realcartest_event_0037', 'realcartest_event_0029', 'realcartest_event_0033']
- B7 hits but Ours misses: ['realcartest_event_0034', 'realcartest_event_0022']

#### Anti-case realcartest_event_0034 (budget=10)
- Event: 760.0s - 770.7s, duration=10.7s
- B7 discovers this event but Ours does not.
- Possible reasons: Ours audit budget too high, repair utility mis-ranks neighbors, or sampling variance.

#### Anti-case realcartest_event_0022 (budget=10)
- Event: 30.0s - 50.7s, duration=20.7s
- B7 discovers this event but Ours does not.
- Possible reasons: Ours audit budget too high, repair utility mis-ranks neighbors, or sampling variance.

## Budget = 20
### Long-interval events
- Ours hits but B7 misses: []
- Both hit: ['realcartest_event_0034', 'realcartest_event_0028', 'realcartest_event_0022', 'realcartest_event_0037', 'realcartest_event_0029', 'realcartest_event_0033']
- B7 hits but Ours misses: []

## Budget = 40
### Long-interval events
- Ours hits but B7 misses: []
- Both hit: ['realcartest_event_0034', 'realcartest_event_0028', 'realcartest_event_0037', 'realcartest_event_0022', 'realcartest_event_0029', 'realcartest_event_0033']
- B7 hits but Ours misses: []

## Budget = 80
### Long-interval events
- Ours hits but B7 misses: []
- Both hit: ['realcartest_event_0022', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0028', 'realcartest_event_0037', 'realcartest_event_0029']
- B7 hits but Ours misses: []

## Summary
1. **Ours-only long hits** exist at multiple budgets, especially 40 and 80.
2. Some Ours-only hits fall inside `E0_top20`, suggesting they could be due to the initial envelope rather than repair.
3. The current log does not record `source_action`, so we cannot causally attribute gains to `audit_triggered_repair`.
4. **Recommendation**: add full repair trace logging in the next implementation before making stronger causal claims.
