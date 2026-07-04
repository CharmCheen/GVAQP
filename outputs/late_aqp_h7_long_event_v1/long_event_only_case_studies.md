# Long-Event-Only Case Studies

Budget=40. Comparing B7 (chunk_size=120.0s, k=3.0) vs Ours-full (E0=top30).

## realcartest_event_0022
- Time range: 30.0s – 50.7s
- Duration: 20.7s
- Inside E0: top10=False, top20=False, top30=False
- B7 hit rate: 6/10, mean best IoU=0.483
- Ours hit rate: 2/10, mean best IoU=0.023
- B7 selected bins (example): ['30-40s', '40-50s', '50-60s']
- Ours selected bins (example): ['50-60s']
- **Interpretation**: B7 is more consistently hitting this event (counter-example).
- Repair trace: not recoverable from current logs

## realcartest_event_0028
- Time range: 380.0s – 400.7s
- Duration: 20.7s
- Inside E0: top10=False, top20=False, top30=False
- B7 hit rate: 3/10, mean best IoU=0.483
- Ours hit rate: 1/10, mean best IoU=0.483
- B7 selected bins (example): ['380-390s', '390-400s', '400-410s']
- Ours selected bins (example): ['380-390s']
- **Interpretation**: B7 is more consistently hitting this event (counter-example).
- Repair trace: not recoverable from current logs

## realcartest_event_0029
- Time range: 490.0s – 500.7s
- Duration: 10.7s
- Inside E0: top10=True, top20=True, top30=True
- B7 hit rate: 8/10, mean best IoU=0.935
- Ours hit rate: 10/10, mean best IoU=0.935
- B7 selected bins (example): ['490-500s', '500-510s']
- Ours selected bins (example): ['490-500s', '500-510s']
- **Interpretation**: Ours is more consistently hitting this event.
- Repair trace: not recoverable from current logs

## realcartest_event_0033
- Time range: 700.0s – 710.7s
- Duration: 10.7s
- Inside E0: top10=False, top20=True, top30=True
- B7 hit rate: 3/10, mean best IoU=0.935
- Ours hit rate: 10/10, mean best IoU=0.395
- B7 selected bins (example): ['700-710s', '710-720s']
- Ours selected bins (example): ['700-710s', '710-720s']
- **Interpretation**: Ours is more consistently hitting this event.
- Repair trace: not recoverable from current logs

## realcartest_event_0034
- Time range: 760.0s – 770.7s
- Duration: 10.7s
- Inside E0: top10=False, top20=False, top30=True
- B7 hit rate: 7/10, mean best IoU=0.935
- Ours hit rate: 10/10, mean best IoU=0.935
- B7 selected bins (example): ['760-770s', '770-780s']
- Ours selected bins (example): ['760-770s']
- **Interpretation**: Ours is more consistently hitting this event.
- Repair trace: not recoverable from current logs

## realcartest_event_0037
- Time range: 830.0s – 880.7s
- Duration: 50.7s
- Inside E0: top10=True, top20=True, top30=True
- B7 hit rate: 6/10, mean best IoU=0.197
- Ours hit rate: 10/10, mean best IoU=0.197
- B7 selected bins (example): ['830-840s', '840-850s', '850-860s', '860-870s', '870-880s', '880-890s']
- Ours selected bins (example): ['840-850s', '850-860s', '860-870s', '870-880s', '880-890s']
- **Interpretation**: Ours is more consistently hitting this event.
- Repair trace: not recoverable from current logs
