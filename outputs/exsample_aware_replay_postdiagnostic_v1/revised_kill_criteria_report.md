# Revised Kill Criteria Report

## KC1: Is Ours fully explained by B7?
- **NOT triggered** on long events: Ours=0.728 vs B7=0.564.

## KC2: Is Ours gain from selecting more duration?
- **NOT triggered**: Ours selects 400.0s vs B7 400.0s (within 20%).

## KC3: Is Ours gain mainly from point-anchor hits?
- **NOT triggered**: point-anchor gain = 0.078, long-event gain = 0.164.

## KC4: Is calibration missing?
- **TRIGGERED**: H7 remains unverified; no exhaustive human annotation exists. Cannot claim calibrated missing-mass estimation.

## KC5: Is budget=40 advantage parameter-stable?
- **NOT triggered**: coefficient of variation = 0.03; advantage is relatively stable.

## KC6: Is complete-event coverage sufficient?
- **TRIGGERED**: long-event complete coverage at budget=40 = 0.000 < 0.5.
- Note: This metric requires a selected interval to fully contain the event. With 10s bins and long events spanning multiple bins, this is a very strict criterion. Low coverage does not necessarily mean repair failed, but it limits how strongly we can claim 'full interval reconstruction'.

## Final Recommendation

- **Primary recommendation**: continue but pivot to dual-ledger calibration
- **Secondary recommendation**: Conduct exhaustive calibration annotation (H7) before any stronger repair claim; also consider a long-event-only replay to isolate structure-repair effects from point-anchor seed discovery.
