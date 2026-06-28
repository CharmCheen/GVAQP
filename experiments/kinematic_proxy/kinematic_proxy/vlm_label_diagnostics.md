# VLM Label Mapping Diagnostics

- VLM source file path: /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/qwen3_vl_32b_round2_5k_raw_fps1_review.csv
- original VLM window count: 67
- proxy clip count: 102
- valid mapped label count: 98
- invalid count: 4
- positive count: 62
- positive rate: 0.633
- strict label availability: False (no usable risk_level rank or affected_ego/ego_related field in current raw 32B source)
- high-confidence label availability: True (explicit yes/no relevance or confidence field available)

## Adjacent Label Transitions

- positive->positive: 57
- positive->negative: 5
- negative->positive: 4
- negative->negative: 31
- average positive run length: 12.400 clips

## Mapping Table

| proxy_clip_id | mapped_vlm_window_id | overlap_ratio | label |
|---|---|---:|---:|
| realcartest_5k_clip00000_s000000000ms_e000005000ms | nan | 0.000 | -1 |
| realcartest_5k_clip00001_s000002000ms_e000007000ms | nan | 0.000 | -1 |
| realcartest_5k_clip00002_s000004000ms_e000009000ms | nan | 0.000 | -1 |
| realcartest_5k_clip00003_s000006000ms_e000011000ms | nan | 0.200 | -1 |
| realcartest_5k_clip00004_s000008000ms_e000013000ms | realcartest_5k_s000010_e000016 | 0.600 | 1 |
| realcartest_5k_clip00005_s000010000ms_e000015000ms | realcartest_5k_s000010_e000016 | 1.000 | 1 |
| realcartest_5k_clip00006_s000012000ms_e000017000ms | realcartest_5k_s000010_e000016 | 0.800 | 1 |
| realcartest_5k_clip00007_s000014000ms_e000019000ms | realcartest_5k_s000013_e000019 | 1.000 | 1 |
| realcartest_5k_clip00008_s000016000ms_e000021000ms | realcartest_5k_s000016_e000022 | 1.000 | 1 |
| realcartest_5k_clip00009_s000018000ms_e000023000ms | realcartest_5k_s000016_e000022 | 0.800 | 1 |
| realcartest_5k_clip00010_s000020000ms_e000025000ms | realcartest_5k_s000019_e000025 | 1.000 | 1 |
| realcartest_5k_clip00011_s000022000ms_e000027000ms | realcartest_5k_s000022_e000028 | 1.000 | 1 |
| realcartest_5k_clip00012_s000024000ms_e000029000ms | realcartest_5k_s000022_e000028 | 0.800 | 1 |
| realcartest_5k_clip00013_s000026000ms_e000031000ms | realcartest_5k_s000025_e000031 | 1.000 | 1 |
| realcartest_5k_clip00014_s000028000ms_e000033000ms | realcartest_5k_s000028_e000034 | 1.000 | 1 |
| realcartest_5k_clip00015_s000030000ms_e000035000ms | realcartest_5k_s000028_e000034 | 0.800 | 1 |
| realcartest_5k_clip00016_s000032000ms_e000037000ms | realcartest_5k_s000031_e000037 | 1.000 | 1 |
| realcartest_5k_clip00017_s000034000ms_e000039000ms | realcartest_5k_s000034_e000040 | 1.000 | 1 |
| realcartest_5k_clip00018_s000036000ms_e000041000ms | realcartest_5k_s000034_e000040 | 0.800 | 1 |
| realcartest_5k_clip00019_s000038000ms_e000043000ms | realcartest_5k_s000037_e000043 | 1.000 | 1 |
| realcartest_5k_clip00020_s000040000ms_e000045000ms | realcartest_5k_s000040_e000046 | 1.000 | 1 |
| realcartest_5k_clip00021_s000042000ms_e000047000ms | realcartest_5k_s000040_e000046 | 0.800 | 1 |
| realcartest_5k_clip00022_s000044000ms_e000049000ms | realcartest_5k_s000043_e000049 | 1.000 | 1 |
| realcartest_5k_clip00023_s000046000ms_e000051000ms | realcartest_5k_s000046_e000052 | 1.000 | 1 |
| realcartest_5k_clip00024_s000048000ms_e000053000ms | realcartest_5k_s000046_e000052 | 0.800 | 1 |
| realcartest_5k_clip00025_s000050000ms_e000055000ms | realcartest_5k_s000049_e000055 | 1.000 | 1 |
| realcartest_5k_clip00026_s000052000ms_e000057000ms | realcartest_5k_s000052_e000058 | 1.000 | 0 |
| realcartest_5k_clip00027_s000054000ms_e000059000ms | realcartest_5k_s000052_e000058 | 0.800 | 0 |
| realcartest_5k_clip00028_s000056000ms_e000061000ms | realcartest_5k_s000055_e000101 | 1.000 | 1 |
| realcartest_5k_clip00029_s000058000ms_e000063000ms | realcartest_5k_s000058_e000104 | 1.000 | 1 |
| realcartest_5k_clip00030_s000060000ms_e000065000ms | realcartest_5k_s000058_e000104 | 0.800 | 1 |
| realcartest_5k_clip00031_s000062000ms_e000067000ms | realcartest_5k_s000101_e000107 | 1.000 | 1 |
| realcartest_5k_clip00032_s000064000ms_e000069000ms | realcartest_5k_s000104_e000110 | 1.000 | 1 |
| realcartest_5k_clip00033_s000066000ms_e000071000ms | realcartest_5k_s000104_e000110 | 0.800 | 1 |
| realcartest_5k_clip00034_s000068000ms_e000073000ms | realcartest_5k_s000107_e000113 | 1.000 | 1 |
| realcartest_5k_clip00035_s000070000ms_e000075000ms | realcartest_5k_s000110_e000116 | 1.000 | 1 |
| realcartest_5k_clip00036_s000072000ms_e000077000ms | realcartest_5k_s000110_e000116 | 0.800 | 1 |
| realcartest_5k_clip00037_s000074000ms_e000079000ms | realcartest_5k_s000113_e000119 | 1.000 | 1 |
| realcartest_5k_clip00038_s000076000ms_e000081000ms | realcartest_5k_s000116_e000122 | 1.000 | 1 |
| realcartest_5k_clip00039_s000078000ms_e000083000ms | realcartest_5k_s000116_e000122 | 0.800 | 1 |
| realcartest_5k_clip00040_s000080000ms_e000085000ms | realcartest_5k_s000119_e000125 | 1.000 | 1 |
| realcartest_5k_clip00041_s000082000ms_e000087000ms | realcartest_5k_s000122_e000128 | 1.000 | 1 |
| realcartest_5k_clip00042_s000084000ms_e000089000ms | realcartest_5k_s000122_e000128 | 0.800 | 1 |
| realcartest_5k_clip00043_s000086000ms_e000091000ms | realcartest_5k_s000125_e000131 | 1.000 | 1 |
| realcartest_5k_clip00044_s000088000ms_e000093000ms | realcartest_5k_s000128_e000134 | 1.000 | 1 |
| realcartest_5k_clip00045_s000090000ms_e000095000ms | realcartest_5k_s000128_e000134 | 0.800 | 1 |
| realcartest_5k_clip00046_s000092000ms_e000097000ms | realcartest_5k_s000131_e000137 | 1.000 | 1 |
| realcartest_5k_clip00047_s000094000ms_e000099000ms | realcartest_5k_s000134_e000140 | 1.000 | 1 |
| realcartest_5k_clip00048_s000096000ms_e000101000ms | realcartest_5k_s000134_e000140 | 0.800 | 1 |
| realcartest_5k_clip00049_s000098000ms_e000103000ms | realcartest_5k_s000137_e000143 | 1.000 | 1 |
| realcartest_5k_clip00050_s000100000ms_e000105000ms | realcartest_5k_s000140_e000146 | 1.000 | 1 |
| realcartest_5k_clip00051_s000102000ms_e000107000ms | realcartest_5k_s000140_e000146 | 0.800 | 1 |
| realcartest_5k_clip00052_s000104000ms_e000109000ms | realcartest_5k_s000143_e000149 | 1.000 | 1 |
| realcartest_5k_clip00053_s000106000ms_e000111000ms | realcartest_5k_s000146_e000152 | 1.000 | 1 |
| realcartest_5k_clip00054_s000108000ms_e000113000ms | realcartest_5k_s000146_e000152 | 0.800 | 1 |
| realcartest_5k_clip00055_s000110000ms_e000115000ms | realcartest_5k_s000149_e000155 | 1.000 | 1 |
| realcartest_5k_clip00056_s000112000ms_e000117000ms | realcartest_5k_s000152_e000158 | 1.000 | 1 |
| realcartest_5k_clip00057_s000114000ms_e000119000ms | realcartest_5k_s000152_e000158 | 0.800 | 1 |
| realcartest_5k_clip00058_s000116000ms_e000121000ms | realcartest_5k_s000155_e000201 | 1.000 | 0 |
| realcartest_5k_clip00059_s000118000ms_e000123000ms | realcartest_5k_s000158_e000204 | 1.000 | 0 |
| realcartest_5k_clip00060_s000120000ms_e000125000ms | realcartest_5k_s000158_e000204 | 0.800 | 0 |
| realcartest_5k_clip00061_s000122000ms_e000127000ms | realcartest_5k_s000201_e000207 | 1.000 | 0 |
| realcartest_5k_clip00062_s000124000ms_e000129000ms | realcartest_5k_s000204_e000210 | 1.000 | 0 |
| realcartest_5k_clip00063_s000126000ms_e000131000ms | realcartest_5k_s000204_e000210 | 0.800 | 0 |
| realcartest_5k_clip00064_s000128000ms_e000133000ms | realcartest_5k_s000207_e000213 | 1.000 | 0 |
| realcartest_5k_clip00065_s000130000ms_e000135000ms | realcartest_5k_s000210_e000216 | 1.000 | 0 |
| realcartest_5k_clip00066_s000132000ms_e000137000ms | realcartest_5k_s000210_e000216 | 0.800 | 0 |
| realcartest_5k_clip00067_s000134000ms_e000139000ms | realcartest_5k_s000213_e000219 | 1.000 | 0 |
| realcartest_5k_clip00068_s000136000ms_e000141000ms | realcartest_5k_s000216_e000222 | 1.000 | 0 |
| realcartest_5k_clip00069_s000138000ms_e000143000ms | realcartest_5k_s000216_e000222 | 0.800 | 0 |
| realcartest_5k_clip00070_s000140000ms_e000145000ms | realcartest_5k_s000219_e000225 | 1.000 | 0 |
| realcartest_5k_clip00071_s000142000ms_e000147000ms | realcartest_5k_s000222_e000228 | 1.000 | 0 |
| realcartest_5k_clip00072_s000144000ms_e000149000ms | realcartest_5k_s000222_e000228 | 0.800 | 0 |
| realcartest_5k_clip00073_s000146000ms_e000151000ms | realcartest_5k_s000225_e000231 | 1.000 | 0 |
| realcartest_5k_clip00074_s000148000ms_e000153000ms | realcartest_5k_s000228_e000234 | 1.000 | 0 |
| realcartest_5k_clip00075_s000150000ms_e000155000ms | realcartest_5k_s000228_e000234 | 0.800 | 0 |
| realcartest_5k_clip00076_s000152000ms_e000157000ms | realcartest_5k_s000231_e000237 | 1.000 | 0 |
| realcartest_5k_clip00077_s000154000ms_e000159000ms | realcartest_5k_s000234_e000240 | 1.000 | 0 |
| realcartest_5k_clip00078_s000156000ms_e000161000ms | realcartest_5k_s000234_e000240 | 0.800 | 0 |
| realcartest_5k_clip00079_s000158000ms_e000163000ms | realcartest_5k_s000237_e000243 | 1.000 | 0 |
| realcartest_5k_clip00080_s000160000ms_e000165000ms | realcartest_5k_s000240_e000246 | 1.000 | 1 |
| realcartest_5k_clip00081_s000162000ms_e000167000ms | realcartest_5k_s000240_e000246 | 0.800 | 1 |
| realcartest_5k_clip00082_s000164000ms_e000169000ms | realcartest_5k_s000243_e000249 | 1.000 | 1 |
| realcartest_5k_clip00083_s000166000ms_e000171000ms | realcartest_5k_s000246_e000252 | 1.000 | 1 |
| realcartest_5k_clip00084_s000168000ms_e000173000ms | realcartest_5k_s000246_e000252 | 0.800 | 1 |
| realcartest_5k_clip00085_s000170000ms_e000175000ms | realcartest_5k_s000249_e000255 | 1.000 | 1 |
| realcartest_5k_clip00086_s000172000ms_e000177000ms | realcartest_5k_s000252_e000258 | 1.000 | 0 |
| realcartest_5k_clip00087_s000174000ms_e000179000ms | realcartest_5k_s000252_e000258 | 0.800 | 0 |
| realcartest_5k_clip00088_s000176000ms_e000181000ms | realcartest_5k_s000255_e000301 | 1.000 | 0 |
| realcartest_5k_clip00089_s000178000ms_e000183000ms | realcartest_5k_s000258_e000304 | 1.000 | 0 |
| realcartest_5k_clip00090_s000180000ms_e000185000ms | realcartest_5k_s000258_e000304 | 0.800 | 0 |
| realcartest_5k_clip00091_s000182000ms_e000187000ms | realcartest_5k_s000301_e000307 | 1.000 | 0 |
| realcartest_5k_clip00092_s000184000ms_e000189000ms | realcartest_5k_s000304_e000310 | 1.000 | 1 |
| realcartest_5k_clip00093_s000186000ms_e000191000ms | realcartest_5k_s000304_e000310 | 0.800 | 1 |
| realcartest_5k_clip00094_s000188000ms_e000193000ms | realcartest_5k_s000307_e000313 | 1.000 | 1 |
| realcartest_5k_clip00095_s000190000ms_e000195000ms | realcartest_5k_s000310_e000316 | 1.000 | 0 |
| realcartest_5k_clip00096_s000192000ms_e000197000ms | realcartest_5k_s000310_e000316 | 0.800 | 0 |
| realcartest_5k_clip00097_s000194000ms_e000199000ms | realcartest_5k_s000313_e000319 | 1.000 | 1 |
| realcartest_5k_clip00098_s000196000ms_e000201000ms | realcartest_5k_s000316_e000322 | 1.000 | 0 |
| realcartest_5k_clip00099_s000198000ms_e000203000ms | realcartest_5k_s000316_e000322 | 0.800 | 0 |
| realcartest_5k_clip00100_s000200000ms_e000205000ms | realcartest_5k_s000319_e000325 | 1.000 | 0 |
| realcartest_5k_clip00101_s000202000ms_e000207000ms | realcartest_5k_s000322_e000328 | 1.000 | 0 |

## Temporal-Overlap Mapping Risk

- Current labels map 67 original 6s stride3 VLM windows onto 102 5s stride2 proxy clips by time overlap.
- One VLM decision can label multiple overlapping proxy clips, inflating apparent temporal continuity.
- Clip-level recall can therefore over-credit expansion policies that harvest adjacent windows from the same mapped VLM segment.
- Event-level recall is reported to reduce this duplication effect, but exact 102-clip VLM labels remain the cleaner evaluation target.
