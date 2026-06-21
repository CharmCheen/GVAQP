# Exact 102-Clip VLM Label Diagnostics

- VLM source file path: /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/vlm_labels_exact_102.csv
- original VLM window count: 102
- proxy clip count: 102
- valid label count: 102
- invalid count: 0
- positive count: 96
- positive rate: 0.941
- label source mode: exact
- ego-relevant label availability: True
- strict label availability: True (exact labels include vlm_affected_ego and vlm_risk_level)
- high-confidence label availability: False (not used for exact 102-label evaluation)

## Adjacent Label Transitions

- positive->positive: 94
- positive->negative: 1
- negative->positive: 2
- negative->negative: 4
- average positive run length: 48.000 clips

## Mapping Table

| clip_id | relevant | risk_level | affected_ego | event_type | confidence |
|---|---|---|---|---|---|
| realcartest_5k_clip00000_s000000000ms_e000005000ms | no | L0 | false | none | high |
| realcartest_5k_clip00001_s000002000ms_e000007000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00002_s000004000ms_e000009000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00003_s000006000ms_e000011000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00004_s000008000ms_e000013000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00005_s000010000ms_e000015000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00006_s000012000ms_e000017000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00007_s000014000ms_e000019000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00008_s000016000ms_e000021000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00009_s000018000ms_e000023000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00010_s000020000ms_e000025000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00011_s000022000ms_e000027000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00012_s000024000ms_e000029000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00013_s000026000ms_e000031000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00014_s000028000ms_e000033000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00015_s000030000ms_e000035000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00016_s000032000ms_e000037000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00017_s000034000ms_e000039000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00018_s000036000ms_e000041000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00019_s000038000ms_e000043000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00020_s000040000ms_e000045000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00021_s000042000ms_e000047000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00022_s000044000ms_e000049000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00023_s000046000ms_e000051000ms | yes | L1 | true | dense_traffic_only | high |
| realcartest_5k_clip00024_s000048000ms_e000053000ms | yes | L1 | true | dense_traffic_only | high |
| realcartest_5k_clip00025_s000050000ms_e000055000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00026_s000052000ms_e000057000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00027_s000054000ms_e000059000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00028_s000056000ms_e000061000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00029_s000058000ms_e000063000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00030_s000060000ms_e000065000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00031_s000062000ms_e000067000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00032_s000064000ms_e000069000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00033_s000066000ms_e000071000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00034_s000068000ms_e000073000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00035_s000070000ms_e000075000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00036_s000072000ms_e000077000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00037_s000074000ms_e000079000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00038_s000076000ms_e000081000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00039_s000078000ms_e000083000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00040_s000080000ms_e000085000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00041_s000082000ms_e000087000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00042_s000084000ms_e000089000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00043_s000086000ms_e000091000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00044_s000088000ms_e000093000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00045_s000090000ms_e000095000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00046_s000092000ms_e000097000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00047_s000094000ms_e000099000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00048_s000096000ms_e000101000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00049_s000098000ms_e000103000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00050_s000100000ms_e000105000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00051_s000102000ms_e000107000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00052_s000104000ms_e000109000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00053_s000106000ms_e000111000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00054_s000108000ms_e000113000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00055_s000110000ms_e000115000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00056_s000112000ms_e000117000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00057_s000114000ms_e000119000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00058_s000116000ms_e000121000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00059_s000118000ms_e000123000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00060_s000120000ms_e000125000ms | no | L0 | false | none | high |
| realcartest_5k_clip00061_s000122000ms_e000127000ms | no | L0 | false | none | high |
| realcartest_5k_clip00062_s000124000ms_e000129000ms | no | L0 | false | none | high |
| realcartest_5k_clip00063_s000126000ms_e000131000ms | no | L0 | false | none | high |
| realcartest_5k_clip00064_s000128000ms_e000133000ms | no | L0 | false | none | high |
| realcartest_5k_clip00065_s000130000ms_e000135000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00066_s000132000ms_e000137000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00067_s000134000ms_e000139000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00068_s000136000ms_e000141000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00069_s000138000ms_e000143000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00070_s000140000ms_e000145000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00071_s000142000ms_e000147000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00072_s000144000ms_e000149000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00073_s000146000ms_e000151000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00074_s000148000ms_e000153000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00075_s000150000ms_e000155000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00076_s000152000ms_e000157000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00077_s000154000ms_e000159000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00078_s000156000ms_e000161000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00079_s000158000ms_e000163000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00080_s000160000ms_e000165000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00081_s000162000ms_e000167000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00082_s000164000ms_e000169000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00083_s000166000ms_e000171000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00084_s000168000ms_e000173000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00085_s000170000ms_e000175000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00086_s000172000ms_e000177000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00087_s000174000ms_e000179000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00088_s000176000ms_e000181000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00089_s000178000ms_e000183000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00090_s000180000ms_e000185000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00091_s000182000ms_e000187000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00092_s000184000ms_e000189000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00093_s000186000ms_e000191000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00094_s000188000ms_e000193000ms | yes | L2 | true | crossing | high |
| realcartest_5k_clip00095_s000190000ms_e000195000ms | yes | L1 | true | dense_traffic_only | high |
| realcartest_5k_clip00096_s000192000ms_e000197000ms | yes | L1 | false | dense_traffic_only | high |
| realcartest_5k_clip00097_s000194000ms_e000199000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00098_s000196000ms_e000201000ms | yes | L1 | true | close_following | high |
| realcartest_5k_clip00099_s000198000ms_e000203000ms | yes | L1 | false | close_following | high |
| realcartest_5k_clip00100_s000200000ms_e000205000ms | yes | L2 | true | cut_in | high |
| realcartest_5k_clip00101_s000202000ms_e000207000ms | yes | L2 | true | cut_in | high |

## Exact-Label Boundary

- These labels are direct clip_id-level Qwen3-VL-32B pseudo labels for the 102 proxy clips.
- They remove the 67-window overlap-mapping ambiguity but remain VLM pseudo-GT, not human ground truth.
