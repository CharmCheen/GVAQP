# Canonical Reference Summary

Main evaluation uses only true interval events, defined locally as reference events with duration >= 5 seconds.
Point-anchor events, defined as duration <= 2 seconds, are excluded from main TP counts and reported separately.

- Total reference events: `20`
- True interval events: `6`
- Point-anchor-only events: `14`
- Reference gate (`true interval events >= 20`): **FAIL**
- Conclusion scope: **diagnostic only** because the main true interval reference has fewer than 20 events.

True interval duration summary:

| index | duration |
| --- | --- |
| count | 6 |
| mean | 20.7 |
| std | 15.4919 |
| min | 10.7 |
| 25% | 10.7 |
| 50% | 15.7 |
| 75% | 20.7 |
| max | 50.7 |
