# Probe Feature Coverage Audit

Dataset: `probe_set_v1` versus current `cheap_signal_v2` feature tables.

- Common feature coverage window: local `0.000` to `1200.000` seconds.
- Probe rows: `25`
- Coverage status counts: `{'full': 20, 'none': 5}`

No probe metric is currently valid because `probe_set_v1` is unannotated. This audit only reports feature-table time coverage.

| probe_id | local start | local end | coverage fraction | status |
| --- | ---: | ---: | ---: | --- |
| probe_set_v1_0001 | 0.000 | 10.000 | 1.000 | full |
| probe_set_v1_0002 | 60.539 | 70.539 | 1.000 | full |
| probe_set_v1_0003 | 121.078 | 131.078 | 1.000 | full |
| probe_set_v1_0004 | 181.616 | 191.616 | 1.000 | full |
| probe_set_v1_0005 | 242.155 | 252.155 | 1.000 | full |
| probe_set_v1_0006 | 302.694 | 312.694 | 1.000 | full |
| probe_set_v1_0007 | 363.233 | 373.233 | 1.000 | full |
| probe_set_v1_0008 | 423.771 | 433.771 | 1.000 | full |
| probe_set_v1_0009 | 484.310 | 494.310 | 1.000 | full |
| probe_set_v1_0010 | 544.849 | 554.849 | 1.000 | full |
| probe_set_v1_0011 | 605.388 | 615.388 | 1.000 | full |
| probe_set_v1_0012 | 665.926 | 675.926 | 1.000 | full |
| probe_set_v1_0013 | 726.465 | 736.465 | 1.000 | full |
| probe_set_v1_0014 | 787.004 | 797.004 | 1.000 | full |
| probe_set_v1_0015 | 847.543 | 857.543 | 1.000 | full |
| probe_set_v1_0016 | 908.082 | 918.082 | 1.000 | full |
| probe_set_v1_0017 | 968.620 | 978.620 | 1.000 | full |
| probe_set_v1_0018 | 1029.159 | 1039.159 | 1.000 | full |
| probe_set_v1_0019 | 1089.698 | 1099.698 | 1.000 | full |
| probe_set_v1_0020 | 1150.237 | 1160.237 | 1.000 | full |
| probe_set_v1_0021 | 1210.775 | 1220.775 | 0.000 | none |
| probe_set_v1_0022 | 1271.314 | 1281.314 | 0.000 | none |
| probe_set_v1_0023 | 1331.853 | 1341.853 | 0.000 | none |
| probe_set_v1_0024 | 1392.392 | 1402.392 | 0.000 | none |
| probe_set_v1_0025 | 1452.930 | 1462.930 | 0.000 | none |
