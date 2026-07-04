# Budget=40 Case Study

Comparing B7 (chunk_size=120.0s, k=3.0) vs Ours-full (E0=top30).

## Event hit counts (across 10 trials)

- Hit by both: 15 events → ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0035', 'realcartest_event_0036', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0039', 'realcartest_event_0040']
- Hit only by Ours-full: 1 events → ['realcartest_event_0041']
- Hit only by B7: 4 events → ['realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0030']
- Hit by neither: 0 events → []

## Events hit only by Ours-full

- **realcartest_event_0041** (point_anchor, duration=0.7s, event interval 1110.0-1110.7s)
  - selected bins: ['1110-1120s']
  - any bin inside top30 E0: True

## Events hit only by B7

- **realcartest_event_0025** (point_anchor, duration=0.2s, event interval 120.5-120.7s)
  - selected bins: ['120-130s']

- **realcartest_event_0026** (point_anchor, duration=0.7s, event interval 250.0-250.7s)
  - selected bins: ['250-260s']

- **realcartest_event_0027** (point_anchor, duration=0.7s, event interval 320.0-320.7s)
  - selected bins: ['320-330s']

- **realcartest_event_0030** (point_anchor, duration=0.7s, event interval 530.0-530.7s)
  - selected bins: ['530-540s']

## Interpretation

- Ours-only events: 0 long-interval, 1 point-anchor.
- All Ours-only events are point-anchor. This weakens the 'temporal structure repair' claim; the gain is better described as event-seed discovery.
