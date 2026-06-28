# Kinematic Proxy Pooled Evaluation

This report evaluates only the manually labeled pooled review set. Labels with `-1` are ignored.

## Precision

| method | labeled_n | Precision@Top-30 | Precision@Top-50 | Positive enrichment vs random@50 | unique positives found |
|---|---:|---:|---:|---:|---:|
| count | 50 | 0.333 | 0.280 | 2.000 | 1 |
| naive | 50 | 0.333 | 0.300 | 2.143 | 2 |
| kinematic | 50 | 0.200 | 0.180 | 1.286 | 0 |
| random | 50 | 0.200 | 0.140 | 1.000 | 0 |

## Method Overlap

| methods | overlap_n |
|---|---:|
| count & naive | 38 |
| count & kinematic | 28 |
| count & random | 27 |
| naive & kinematic | 31 |
| naive & random | 26 |
| kinematic & random | 28 |

## False Positive Cases

| clip_id | selected_by | notes |
|---|---|---|
| realcartest_5k_clip00004_s000008000ms_e000013000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00010_s000020000ms_e000025000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00011_s000022000ms_e000027000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00015_s000030000ms_e000035000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00016_s000032000ms_e000037000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00019_s000038000ms_e000043000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00021_s000042000ms_e000047000ms | kinematic|naive | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00022_s000044000ms_e000049000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00024_s000048000ms_e000053000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00025_s000050000ms_e000055000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00026_s000052000ms_e000057000ms | kinematic|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00027_s000054000ms_e000059000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00028_s000056000ms_e000061000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00029_s000058000ms_e000063000ms | kinematic|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00030_s000060000ms_e000065000ms | kinematic|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00031_s000062000ms_e000067000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00032_s000064000ms_e000069000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00034_s000068000ms_e000073000ms | kinematic|naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00040_s000080000ms_e000085000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00041_s000082000ms_e000087000ms | kinematic|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00044_s000088000ms_e000093000ms | kinematic|naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00045_s000090000ms_e000095000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00046_s000092000ms_e000097000ms | kinematic|naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00058_s000116000ms_e000121000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00066_s000132000ms_e000137000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00067_s000134000ms_e000139000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00068_s000136000ms_e000141000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00069_s000138000ms_e000143000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00070_s000140000ms_e000145000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00071_s000142000ms_e000147000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00076_s000152000ms_e000157000ms | kinematic|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00079_s000158000ms_e000163000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00085_s000170000ms_e000175000ms | kinematic|naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00087_s000174000ms_e000179000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00088_s000176000ms_e000181000ms | kinematic|naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00089_s000178000ms_e000183000ms | kinematic|naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00090_s000180000ms_e000185000ms | kinematic|naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00091_s000182000ms_e000187000ms | kinematic|naive | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00098_s000196000ms_e000201000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00099_s000198000ms_e000203000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00100_s000200000ms_e000205000ms | kinematic | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00012_s000024000ms_e000029000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00018_s000036000ms_e000041000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00023_s000046000ms_e000051000ms | naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00035_s000070000ms_e000075000ms | naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00036_s000072000ms_e000077000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00037_s000074000ms_e000079000ms | naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00038_s000076000ms_e000081000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00039_s000078000ms_e000083000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00042_s000084000ms_e000089000ms | naive|count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00043_s000086000ms_e000091000ms | naive|count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00077_s000154000ms_e000159000ms | naive | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00086_s000172000ms_e000177000ms | naive|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00002_s000004000ms_e000009000ms | count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00003_s000006000ms_e000011000ms | count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00013_s000026000ms_e000031000ms | count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00014_s000028000ms_e000033000ms | count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00017_s000034000ms_e000039000ms | count | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
| realcartest_5k_clip00095_s000190000ms_e000195000ms | count|random | negative: no clear vehicle cut-in or ego-path intrusion in sampled frames |
