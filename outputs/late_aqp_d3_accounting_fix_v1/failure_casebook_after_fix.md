# Failure Casebook After Accounting Fix


## Fix improved D3-core over original: dataset3_0_1200 budget=80 seed=0

- **LATE-D3-core-chunk120** budget=80 seed=0
  - event_recall=1.000, unique_events_hit=6.0
  - repair_calls=0, audit_calls=6, discovery_calls=71, guard_calls=2
  - selected core intervals: [500.0,510.0], [570.0,580.0], [600.0,610.0], [680.0,700.0], [750.0,760.0], [830.0,840.0]
  - hit events: ['dataset3_event_000', 'dataset3_event_001', 'dataset3_event_002', 'dataset3_event_003', 'dataset3_event_004', 'dataset3_event_005']
  - missed events: []
- **D3-core-chunk120-fixed** budget=80 seed=0
  - event_recall=1.000, unique_events_hit=6.0
  - repair_calls=0, audit_calls=6, discovery_calls=72, guard_calls=2
  - selected core intervals: [500.0,510.0], [570.0,580.0], [600.0,610.0], [680.0,700.0], [750.0,760.0], [830.0,840.0]
  - hit events: ['dataset3_event_000', 'dataset3_event_001', 'dataset3_event_002', 'dataset3_event_003', 'dataset3_event_004', 'dataset3_event_005']
  - missed events: []

## D3-core-fixed still lags D3-norepair: realcartest_2000_3200 budget=40 seed=0

- **D3-core-chunk120-fixed** budget=40 seed=0
  - event_recall=0.100, unique_events_hit=2.0
  - repair_calls=0, audit_calls=4, discovery_calls=21, guard_calls=4
  - selected core intervals: [760.0,780.0], [1110.0,1120.0]
  - hit events: ['realcartest_event_0034', 'realcartest_event_0041']
  - missed events: ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0030', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0035', 'realcartest_event_0036', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0039', 'realcartest_event_0040']
- **D3-norepair-core-chunk120** budget=40 seed=0
  - event_recall=0.350, unique_events_hit=7.0
  - repair_calls=0, audit_calls=0, discovery_calls=32, guard_calls=8
  - selected core intervals: [30.0,60.0], [70.0,80.0], [90.0,100.0], [840.0,890.0], [960.0,970.0], [1060.0,1070.0], [1110.0,1120.0]
  - hit events: ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0040', 'realcartest_event_0041']
  - missed events: ['realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0030', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0035', 'realcartest_event_0036', 'realcartest_event_0039']

## B7-core beats D3-core-fixed: realcartest_3200_3830 budget=19 seed=0

- **D3-core-chunk120-fixed** budget=19 seed=0
  - event_recall=0.286, unique_events_hit=2.0
  - repair_calls=0, audit_calls=2, discovery_calls=10, guard_calls=5
  - selected core intervals: [510.0,530.0], [580.0,590.0]
  - hit events: ['realcartest_event_0047', 'realcartest_event_0048']
  - missed events: ['realcartest_event_0042', 'realcartest_event_0043', 'realcartest_event_0044', 'realcartest_event_0045', 'realcartest_event_0046']
- **B7-core** budget=19 seed=0
  - event_recall=0.571, unique_events_hit=4.0
  - repair_calls=0, audit_calls=0, discovery_calls=12, guard_calls=5
  - selected core intervals: [0.0,40.0], [450.0,460.0], [480.0,500.0], [510.0,530.0]
  - hit events: ['realcartest_event_0042', 'realcartest_event_0045', 'realcartest_event_0046', 'realcartest_event_0047']
  - missed events: ['realcartest_event_0043', 'realcartest_event_0044', 'realcartest_event_0048']

## D3-core-fixed beats D3-norepair: realcartest_0_1570 budget=40 seed=0

- **D3-norepair-core-chunk120** budget=40 seed=0
  - event_recall=0.000, unique_events_hit=0.0
  - repair_calls=0, audit_calls=0, discovery_calls=0, guard_calls=0
  - selected core intervals: 
  - hit events: []
  - missed events: ['realcartest_event_0000', 'realcartest_event_0001', 'realcartest_event_0002', 'realcartest_event_0003', 'realcartest_event_0004', 'realcartest_event_0005', 'realcartest_event_0006', 'realcartest_event_0007', 'realcartest_event_0008', 'realcartest_event_0009', 'realcartest_event_0010', 'realcartest_event_0011', 'realcartest_event_0012', 'realcartest_event_0013', 'realcartest_event_0014', 'realcartest_event_0015', 'realcartest_event_0016', 'realcartest_event_0017', 'realcartest_event_0018', 'realcartest_event_0019']
- **D3-core-chunk120-fixed** budget=40 seed=0
  - event_recall=0.200, unique_events_hit=4.0
  - repair_calls=0, audit_calls=4, discovery_calls=25, guard_calls=11
  - selected core intervals: [10.0,110.0], [550.0,590.0], [1210.0,1230.0], [1250.0,1260.0]
  - hit events: ['realcartest_event_0000', 'realcartest_event_0006', 'realcartest_event_0017', 'realcartest_event_0018']
  - missed events: ['realcartest_event_0001', 'realcartest_event_0002', 'realcartest_event_0003', 'realcartest_event_0004', 'realcartest_event_0005', 'realcartest_event_0007', 'realcartest_event_0008', 'realcartest_event_0009', 'realcartest_event_0010', 'realcartest_event_0011', 'realcartest_event_0012', 'realcartest_event_0013', 'realcartest_event_0014', 'realcartest_event_0015', 'realcartest_event_0016', 'realcartest_event_0019']

## Aggregate summary: fix improved D3-core over original

- realcartest_0_1570 budget=40: fixed R=0.400 vs orig R=0.050 (+0.350), unique events 8.0 vs 1.0
- realcartest_2000_3200 budget=40: fixed R=0.550 vs orig R=0.100 (+0.450), unique events 11.0 vs 2.0
- realcartest_3200_3830 budget=20: fixed R=0.429 vs orig R=0.000 (+0.429), unique events 3.0 vs 0.0
- dataset3_0_1200 budget=80: fixed R=1.000 vs orig R=0.333 (+0.667), unique events 6.0 vs 2.0
- dataset3_1200_2400 budget=100: fixed R=1.000 vs orig R=0.667 (+0.333), unique events 12.0 vs 8.0
- dataset3_2400_3462 budget=60: fixed R=0.556 vs orig R=0.111 (+0.444), unique events 5.0 vs 1.0

## Aggregate summary: D3-core-fixed still lags D3-norepair

- realcartest_0_1570 budget=40: fixed R=0.050 vs norepair R=0.400 (-0.350), unique events 1.0 vs 8.0
- realcartest_2000_3200 budget=40: fixed R=0.050 vs norepair R=0.450 (-0.400), unique events 1.0 vs 9.0
- realcartest_3200_3830 budget=20: fixed R=0.000 vs norepair R=0.714 (-0.714), unique events 0.0 vs 5.0
- dataset3_0_1200 budget=40: fixed R=0.000 vs norepair R=0.833 (-0.833), unique events 0.0 vs 5.0
- dataset3_1200_2400 budget=90: fixed R=0.417 vs norepair R=1.000 (-0.583), unique events 5.0 vs 12.0
- dataset3_2400_3462 budget=60: fixed R=0.222 vs norepair R=0.778 (-0.556), unique events 2.0 vs 7.0

## Aggregate summary: B7-core beats D3-core-fixed

- realcartest_0_1570 budget=80: fixed R=0.250 vs B7 R=0.550
- realcartest_2000_3200 budget=40: fixed R=0.050 vs B7 R=0.400
- realcartest_3200_3830 budget=19: fixed R=0.000 vs B7 R=0.571
- dataset3_0_1200 budget=24: fixed R=0.000 vs B7 R=0.500
- dataset3_1200_2400 budget=40: fixed R=0.083 vs B7 R=0.500
- dataset3_2400_3462 budget=60: fixed R=0.222 vs B7 R=0.778
