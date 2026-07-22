# Authoritative input recovery

The governing C0 target is 80% canonical-event recall and total cost strictly
below 70% of the 347-call dense audit. No event-F1 threshold is present. Binary,
proxy best-first ANY and exact count-guided semantics reproduce from the frozen
simulator. The primary exact count-guided ceiling uses COUNT x1.25, 85 interval
calls and 21 certifications; it has constant ratio 0.366715, linear-duration
ratio 4.494957, grid break-even alpha 0.95 and continuous alpha 0.919267.

Intervals are binary-tree ranges over 347 ten-second units. Existing narrative
recommends physical 10/30/60/120-second measurements, while the later physical
brief proposed 20/40/80/160 seconds if no matrix was frozen. This amendment does
not create a physical sample, so it freezes per-length accuracy requirements for
every later tested length rather than resolving that sampling choice post hoc.

Gate A remains `UNIT_ORACLE_DARE_ACCELERATION_NO_GO`; the previous physical gate
is `INTERVAL_OPERATOR_CONTRACT_BLOCKED`, with zero physical responses. All input
hashes are recorded before derivation in `config/SOURCE_MANIFEST.csv` and
`config/INPUT_MANIFEST.csv`.
