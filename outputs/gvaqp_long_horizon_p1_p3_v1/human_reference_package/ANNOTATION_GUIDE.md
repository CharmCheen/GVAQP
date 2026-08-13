# Independent temporal-event annotation guide

For each video/query case, watch the full video (you may seek freely) and record every temporal episode that satisfies the frozen query definition. An event is a maximal continuous semantic episode, not a fixed 10-second unit. Do not use model predictions, candidate scores, previous event references, selection traces, or any method results.

For every event, record: `event_exists`, `start_time`, `end_time`, and whether either boundary is ambiguous. Use seconds as shown by the player. When a boundary is uncertain, record your best estimate and set `boundary_ambiguous=true`; do not delete a clearly present event merely because its edge is gradual. If no event occurs, submit an empty event list and `event_exists=false`.

Each annotator must complete all six cases independently. A second annotator should use a different `annotator_id`; adjudication is performed only after both submissions are frozen. The interface never displays semantic-oracle outcomes, C1/K3 events, proxy scores, trace identities, or study results.
