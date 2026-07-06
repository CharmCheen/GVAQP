# Repair Negative Case Studies

Each case shows the call sequence for one trial. `repair` calls are highlighted.


## Case: realcartest_3200_3830 budget=10 seed=0

- event_recall_diff (core - nr): -0.571
- unique_bin_diff: -8
- repair_calls: 0

| idx | type | bin | chunk | label | prior | best_alt_chunk | best_alt_theta |
|---|---|---|---|---|---|---|---|
| 0 | audit | 62 | 5 | negative | 0.729 | 0.0 | 0.100 |
| 1 | discovery | 12 | 1 | negative | 0.463 | 0.0 | 0.100 |
| 2 | discovery | 8 | 0 | negative | 0.671 | 2.0 | 0.100 |
| 3 | discovery | 9 | 0 | negative | 0.906 | 2.0 | 0.100 |
| 4 | discovery | 52 | 4 | positive | 0.708 | 2.0 | 0.100 |
| 5 | discovery | 58 | 4 | positive | 1.000 | 2.0 | 0.100 |
| 6 | discovery | 50 | 4 | negative | 0.895 | 2.0 | 0.100 |
| 7 | discovery | 59 | 4 | negative | 1.000 | 2.0 | 0.100 |
| 8 | discovery | 56 | 4 | negative | 0.431 | 2.0 | 0.100 |
| 9 | discovery | 48 | 4 | positive | 0.563 | 2.0 | 0.100 |
| 10 | discovery | 22 | 1 | negative | 0.716 | 0.0 | 0.100 |

## Case: dataset3_2400_3462 budget=106 seed=0

- event_recall_diff (core - nr): -0.222
- unique_bin_diff: -5
- repair_calls: 2

| idx | type | bin | chunk | label | prior | best_alt_chunk | best_alt_theta |
|---|---|---|---|---|---|---|---|
| 0 | audit | 104 | 8 | negative | 1.741 | 0.0 | 0.100 |
| 1 | audit | 76 | 6 | negative | 2.043 | 0.0 | 0.100 |
| 2 | audit | 62 | 5 | negative | 1.741 | 0.0 | 0.100 |
| 3 | audit | 96 | 8 | negative | 0.535 | 0.0 | 0.100 |
| 4 | audit | 82 | 6 | positive | 0.836 | 0.0 | 0.100 |
| 5 | audit | 42 | 3 | negative | 0.836 | 6.0 | 0.367 |
| 6 | audit | 11 | 0 | negative | 2.948 | 6.0 | 0.367 |
| 7 | audit | 7 | 0 | positive | 2.345 | 6.0 | 0.367 |
| 8 | audit | 79 | 6 | negative | 1.741 | 0.0 | 0.367 |
| 9 | audit | 65 | 5 | negative | 1.741 | 0.0 | 0.367 |
| 10 | audit | 66 | 5 | negative | 2.043 | 0.0 | 0.367 |
| 11 | audit | 12 | 1 | negative | 1.440 | 0.0 | 0.367 |
| 12 | audit | 13 | 1 | positive | 0.836 | 0.0 | 0.367 |
| 13 | audit | 95 | 7 | negative | 1.138 | 0.0 | 0.367 |
| 14 | audit | 81 | 6 | negative | 1.440 | 0.0 | 0.367 |
| 15 | audit | 75 | 6 | negative | 1.440 | 0.0 | 0.367 |
| 16 | audit | 52 | 4 | negative | 0.836 | 0.0 | 0.367 |
| 17 | audit | 6 | 0 | positive | 1.138 | 1.0 | 0.367 |
| 18 | audit | 73 | 6 | negative | 0.535 | 0.0 | 0.525 |
| 19 | audit | 38 | 3 | negative | 0.836 | 0.0 | 0.525 |
| 20 | audit | 102 | 8 | negative | 1.138 | 0.0 | 0.525 |
| 21 | audit | 67 | 5 | negative | 0.836 | 0.0 | 0.525 |
| 22 | audit | 63 | 5 | negative | 0.836 | 0.0 | 0.525 |
| 23 | audit | 5 | 0 | negative | 0.836 | 1.0 | 0.367 |
| 24 | audit | 105 | 8 | negative | 0.836 | 0.0 | 0.420 |
| 25 | audit | 9 | 0 | negative | 1.138 | 1.0 | 0.367 |
| 26 | repair | 83 | 6 | negative | -0.672 | 1.0 | 0.367 |
| 27 | repair | 14 | 1 | positive | -0.672 | 0.0 | 0.350 |
| 28 | discovery | 97 | 8 | negative | -0.672 | 0.0 | 0.100 |
| 29 | discovery | 7 | 0 | positive | 2.345 | 1.0 | 0.100 |
| 30 | discovery | 10 | 0 | negative | 2.043 | 1.0 | 0.100 |
| 31 | discovery | 5 | 0 | negative | 0.836 | 1.0 | 0.100 |
| 32 | discovery | 64 | 5 | negative | -0.370 | 0.0 | 0.275 |
| 33 | discovery | 65 | 5 | negative | 1.741 | 0.0 | 0.275 |
| 34 | discovery | 4 | 0 | negative | 1.440 | 1.0 | 0.100 |
| 35 | discovery | 98 | 8 | negative | -0.672 | 0.0 | 0.220 |
| 36 | discovery | 90 | 7 | negative | -0.069 | 0.0 | 0.220 |
| 37 | discovery | 86 | 7 | negative | -0.672 | 0.0 | 0.220 |
| 38 | discovery | 6 | 0 | positive | 1.138 | 1.0 | 0.100 |
| 39 | discovery | 8 | 0 | negative | 1.138 | 1.0 | 0.100 |
| 40 | discovery | 3 | 0 | negative | -0.069 | 1.0 | 0.100 |
| 41 | discovery | 35 | 2 | negative | 0.535 | 0.0 | 0.263 |
| 42 | discovery | 0 | 0 | negative | -0.069 | 1.0 | 0.100 |
| 43 | discovery | 11 | 0 | negative | 2.948 | 1.0 | 0.100 |
| 44 | discovery | 45 | 3 | negative | -0.069 | 0.0 | 0.210 |
| 45 | discovery | 31 | 2 | negative | 1.440 | 0.0 | 0.210 |
| 46 | discovery | 82 | 6 | positive | 0.836 | 0.0 | 0.210 |
| 47 | discovery | 2 | 0 | negative | 0.836 | 6.0 | 0.550 |
| 48 | discovery | 57 | 4 | positive | -0.069 | 6.0 | 0.550 |
| 49 | discovery | 73 | 6 | negative | 0.535 | 4.0 | 0.550 |
| 50 | discovery | 54 | 4 | negative | -1.275 | 6.0 | 0.367 |
| 51 | discovery | 14 | 1 | positive | -0.672 | 4.0 | 0.367 |
| 52 | discovery | 47 | 3 | negative | -0.370 | 1.0 | 0.550 |
| 53 | discovery | 58 | 4 | negative | -0.069 | 1.0 | 0.550 |
| 54 | discovery | 50 | 4 | negative | -0.069 | 1.0 | 0.550 |
| 55 | discovery | 1 | 0 | negative | -0.069 | 1.0 | 0.550 |
| 56 | discovery | 20 | 1 | negative | 0.535 | 6.0 | 0.367 |
| 57 | discovery | 52 | 4 | negative | 0.836 | 1.0 | 0.367 |
| 58 | discovery | 18 | 1 | negative | 0.535 | 6.0 | 0.367 |
| 59 | discovery | 16 | 1 | negative | 2.345 | 6.0 | 0.367 |
| 60 | discovery | 74 | 6 | negative | -0.672 | 1.0 | 0.220 |
| 61 | discovery | 23 | 1 | negative | 0.535 | 6.0 | 0.275 |
| 62 | discovery | 51 | 4 | negative | 0.233 | 6.0 | 0.275 |
| 63 | discovery | 80 | 6 | negative | 1.138 | 1.0 | 0.183 |
| 64 | discovery | 13 | 1 | positive | 0.836 | 6.0 | 0.220 |
| 65 | discovery | 83 | 6 | negative | -0.672 | 1.0 | 0.300 |
| 66 | discovery | 28 | 2 | negative | 1.440 | 1.0 | 0.300 |
| 67 | discovery | 12 | 1 | negative | 1.440 | 6.0 | 0.183 |
| 68 | discovery | 9 | 0 | negative | 1.138 | 1.0 | 0.263 |
| 69 | discovery | 15 | 1 | negative | -0.370 | 6.0 | 0.183 |
| 70 | discovery | 59 | 4 | negative | -0.672 | 1.0 | 0.233 |
| 71 | discovery | 72 | 6 | negative | -1.275 | 1.0 | 0.233 |
| 72 | discovery | 101 | 8 | negative | -0.370 | 1.0 | 0.233 |
| 73 | discovery | 103 | 8 | negative | 1.138 | 1.0 | 0.233 |
| 74 | discovery | 61 | 5 | negative | -0.370 | 1.0 | 0.233 |
| 75 | discovery | 17 | 1 | negative | 1.440 | 0.0 | 0.162 |
| 76 | discovery | 81 | 6 | negative | 1.440 | 1.0 | 0.210 |
| 77 | discovery | 63 | 5 | negative | 0.836 | 1.0 | 0.210 |
| 78 | discovery | 78 | 6 | negative | 1.741 | 1.0 | 0.210 |
| 79 | discovery | 41 | 3 | negative | -0.069 | 1.0 | 0.210 |
| 80 | discovery | 22 | 1 | negative | 0.233 | 0.0 | 0.162 |
| 81 | discovery | 21 | 1 | negative | -0.672 | 0.0 | 0.162 |
| 82 | discovery | 19 | 1 | negative | 1.138 | 0.0 | 0.162 |
| 83 | discovery | 56 | 4 | positive | 0.535 | 0.0 | 0.162 |
| 84 | discovery | 100 | 8 | negative | -0.370 | 4.0 | 0.233 |
| 85 | discovery | 49 | 4 | negative | 0.535 | 0.0 | 0.162 |
| 86 | discovery | 77 | 6 | positive | 2.043 | 4.0 | 0.210 |
| 87 | discovery | 79 | 6 | negative | 1.741 | 4.0 | 0.210 |
| 88 | discovery | 76 | 6 | negative | 2.043 | 4.0 | 0.210 |
| 89 | discovery | 75 | 6 | negative | 1.440 | 4.0 | 0.210 |
| 90 | discovery | 84 | 7 | negative | -0.974 | 4.0 | 0.210 |
| 91 | discovery | 53 | 4 | negative | 0.233 | 0.0 | 0.162 |
| 92 | discovery | 55 | 4 | negative | -0.370 | 0.0 | 0.162 |
| 93 | discovery | 48 | 4 | negative | 0.535 | 0.0 | 0.162 |
| 94 | discovery | 62 | 5 | negative | 1.741 | 0.0 | 0.162 |
| 95 | discovery | 25 | 2 | negative | -0.672 | 0.0 | 0.162 |
| 96 | discovery | 24 | 2 | negative | 0.233 | 0.0 | 0.162 |
| 97 | discovery | 92 | 7 | negative | 0.233 | 0.0 | 0.162 |
| 98 | discovery | 44 | 3 | negative | -0.672 | 0.0 | 0.162 |
| 99 | discovery | 46 | 3 | negative | -0.069 | 0.0 | 0.162 |
| 100 | discovery | 67 | 5 | negative | 0.836 | 0.0 | 0.162 |
| 101 | discovery | 30 | 2 | negative | -0.974 | 0.0 | 0.162 |
| 102 | discovery | 39 | 3 | negative | 0.836 | 0.0 | 0.162 |
| 103 | discovery | 106 | 8 | negative | 0.233 | 0.0 | 0.162 |
| 104 | discovery | 66 | 5 | negative | 2.043 | 0.0 | 0.162 |
| 105 | discovery | 85 | 7 | positive | -1.879 | 0.0 | 0.162 |
| 106 | discovery | 28 | 2 | negative | 1.440 | 0.0 | 0.100 |
| 107 | discovery | 93 | 7 | negative | 1.440 | 0.0 | 0.100 |
| 108 | discovery | 68 | 5 | negative | -0.069 | 0.0 | 0.100 |
| 109 | discovery | 95 | 7 | negative | 1.138 | 0.0 | 0.100 |
| 110 | discovery | 42 | 3 | negative | 0.836 | 0.0 | 0.100 |
| 111 | discovery | 2 | 0 | negative | 0.836 | 1.0 | 0.100 |
| 112 | discovery | 14 | 1 | positive | -0.672 | 4.0 | 0.100 |
| 113 | discovery | 12 | 1 | negative | 1.440 | 4.0 | 0.100 |
| 114 | discovery | 22 | 1 | negative | 0.233 | 4.0 | 0.100 |
| 115 | discovery | 20 | 1 | negative | 0.535 | 4.0 | 0.100 |
| 116 | discovery | 48 | 4 | negative | 0.535 | 1.0 | 0.220 |
| 117 | discovery | 51 | 4 | negative | 0.233 | 1.0 | 0.220 |
| 118 | discovery | 21 | 1 | negative | -0.672 | 6.0 | 0.100 |
| 119 | discovery | 25 | 2 | negative | -0.672 | 1.0 | 0.183 |
| 120 | discovery | 23 | 1 | negative | 0.535 | 6.0 | 0.100 |
| 121 | discovery | 67 | 5 | negative | 0.836 | 1.0 | 0.157 |
| 122 | discovery | 15 | 1 | negative | -0.370 | 6.0 | 0.100 |
| 123 | discovery | 9 | 0 | negative | 1.138 | 1.0 | 0.138 |
| 124 | discovery | 85 | 7 | positive | -1.879 | 1.0 | 0.138 |
| 125 | discovery | 91 | 7 | positive | 0.535 | 1.0 | 0.138 |
| 126 | discovery | 89 | 7 | negative | 0.836 | 1.0 | 0.138 |
| 127 | discovery | 79 | 6 | negative | 1.741 | 7.0 | 0.350 |
| 128 | discovery | 106 | 8 | negative | 0.233 | 7.0 | 0.350 |
| 129 | discovery | 87 | 7 | negative | -0.370 | 1.0 | 0.138 |
| 130 | discovery | 13 | 1 | positive | 0.836 | 7.0 | 0.300 |
| 131 | discovery | 84 | 7 | negative | -0.974 | 1.0 | 0.233 |
| 132 | discovery | 16 | 1 | negative | 2.345 | 7.0 | 0.263 |
| 133 | discovery | 75 | 6 | negative | 1.440 | 7.0 | 0.263 |
| 134 | discovery | 99 | 8 | negative | 1.741 | 7.0 | 0.263 |
| 135 | discovery | 19 | 1 | negative | 1.138 | 7.0 | 0.263 |
| 136 | discovery | 92 | 7 | negative | 0.233 | 1.0 | 0.191 |
| 137 | discovery | 18 | 1 | negative | 0.535 | 7.0 | 0.233 |
| 138 | discovery | 17 | 1 | negative | 1.440 | 7.0 | 0.233 |
| 139 | discovery | 43 | 3 | positive | -0.370 | 7.0 | 0.233 |
| 140 | discovery | 90 | 7 | negative | -0.069 | 3.0 | 0.367 |
| 141 | discovery | 7 | 0 | positive | 2.345 | 3.0 | 0.367 |
| 142 | discovery | 36 | 3 | positive | 1.440 | 0.0 | 0.275 |
| 143 | discovery | 39 | 3 | negative | 0.836 | 0.0 | 0.275 |
| 144 | discovery | 94 | 7 | negative | -0.370 | 3.0 | 0.420 |
| 145 | discovery | 88 | 7 | negative | 0.233 | 3.0 | 0.420 |
| 146 | discovery | 5 | 0 | negative | 0.836 | 3.0 | 0.420 |
| 147 | discovery | 44 | 3 | negative | -0.672 | 0.0 | 0.220 |
| 148 | discovery | 41 | 3 | negative | -0.069 | 0.0 | 0.220 |
| 149 | discovery | 47 | 3 | negative | -0.370 | 0.0 | 0.220 |
| 150 | discovery | 40 | 3 | negative | 1.741 | 0.0 | 0.220 |
| 151 | discovery | 10 | 0 | negative | 2.043 | 3.0 | 0.233 |
| 152 | discovery | 76 | 6 | negative | 2.043 | 3.0 | 0.233 |
| 153 | discovery | 37 | 3 | negative | 0.535 | 0.0 | 0.183 |
| 154 | discovery | 45 | 3 | negative | -0.069 | 0.0 | 0.183 |
| 155 | discovery | 46 | 3 | negative | -0.069 | 0.0 | 0.183 |
| 156 | discovery | 86 | 7 | negative | -0.672 | 0.0 | 0.183 |
| 157 | discovery | 38 | 3 | negative | 0.836 | 0.0 | 0.183 |
| 158 | discovery | 1 | 0 | negative | -0.069 | 1.0 | 0.162 |
| 159 | discovery | 4 | 0 | negative | 1.440 | 1.0 | 0.162 |
| 160 | discovery | 3 | 0 | negative | -0.069 | 1.0 | 0.162 |
| 161 | discovery | 26 | 2 | negative | 0.233 | 1.0 | 0.162 |
| 162 | discovery | 11 | 0 | negative | 2.948 | 1.0 | 0.162 |
| 163 | discovery | 6 | 0 | positive | 1.138 | 1.0 | 0.162 |
| 164 | discovery | 100 | 8 | negative | -0.370 | 0.0 | 0.191 |
| 165 | discovery | 56 | 4 | positive | 0.535 | 0.0 | 0.191 |
| 166 | discovery | 105 | 8 | negative | 0.836 | 4.0 | 0.275 |
| 167 | discovery | 53 | 4 | negative | 0.233 | 0.0 | 0.191 |
| 168 | discovery | 0 | 0 | negative | -0.069 | 4.0 | 0.220 |
| 169 | discovery | 32 | 2 | negative | 0.535 | 4.0 | 0.220 |
| 170 | discovery | 8 | 0 | negative | 1.138 | 4.0 | 0.220 |
| 171 | discovery | 71 | 5 | negative | -0.672 | 4.0 | 0.220 |
| 172 | discovery | 52 | 4 | negative | 0.836 | 0.0 | 0.162 |
| 173 | discovery | 59 | 4 | negative | -0.672 | 0.0 | 0.162 |
| 174 | discovery | 50 | 4 | negative | -0.069 | 0.0 | 0.162 |
| 175 | discovery | 58 | 4 | negative | -0.069 | 0.0 | 0.162 |
| 176 | discovery | 55 | 4 | negative | -0.370 | 0.0 | 0.162 |
| 177 | discovery | 80 | 6 | negative | 1.138 | 0.0 | 0.162 |
| 178 | discovery | 41 | 3 | negative | -0.069 | 0.0 | 0.100 |
| 179 | discovery | 77 | 6 | positive | 2.043 | 0.0 | 0.100 |
| 180 | discovery | 81 | 6 | negative | 1.440 | 0.0 | 0.100 |
| 181 | discovery | 76 | 6 | negative | 2.043 | 0.0 | 0.100 |
| 182 | discovery | 80 | 6 | negative | 1.138 | 0.0 | 0.100 |
| 183 | discovery | 99 | 8 | negative | 1.741 | 6.0 | 0.220 |
| 184 | discovery | 15 | 1 | negative | -0.370 | 6.0 | 0.220 |
| 185 | discovery | 79 | 6 | negative | 1.741 | 0.0 | 0.100 |
| 186 | discovery | 73 | 6 | negative | 0.535 | 0.0 | 0.100 |
| 187 | discovery | 64 | 5 | negative | -0.370 | 6.0 | 0.157 |
| 188 | discovery | 74 | 6 | negative | -0.672 | 0.0 | 0.100 |
| 189 | discovery | 25 | 2 | negative | -0.672 | 6.0 | 0.138 |
| 190 | discovery | 105 | 8 | negative | 0.836 | 6.0 | 0.138 |
| 191 | discovery | 4 | 0 | negative | 1.440 | 6.0 | 0.138 |
| 192 | discovery | 38 | 3 | negative | 0.836 | 6.0 | 0.138 |
| 193 | discovery | 78 | 6 | negative | 1.741 | 4.0 | 0.100 |
| 194 | discovery | 72 | 6 | negative | -1.275 | 4.0 | 0.100 |
| 195 | discovery | 82 | 6 | positive | 0.836 | 4.0 | 0.100 |
| 196 | discovery | 65 | 5 | negative | 1.741 | 6.0 | 0.191 |
| 197 | discovery | 28 | 2 | negative | 1.440 | 6.0 | 0.191 |
| 198 | discovery | 88 | 7 | negative | 0.233 | 6.0 | 0.191 |
| 199 | discovery | 69 | 5 | negative | -0.370 | 6.0 | 0.191 |
| 200 | discovery | 75 | 6 | negative | 1.440 | 4.0 | 0.100 |
| 201 | discovery | 3 | 0 | negative | -0.069 | 6.0 | 0.175 |
| 202 | discovery | 14 | 1 | positive | -0.672 | 6.0 | 0.175 |
| 203 | discovery | 22 | 1 | negative | 0.233 | 6.0 | 0.175 |
| 204 | discovery | 83 | 6 | negative | -0.672 | 1.0 | 0.275 |
| 205 | discovery | 61 | 5 | negative | -0.370 | 1.0 | 0.275 |
| 206 | discovery | 47 | 3 | negative | -0.370 | 1.0 | 0.275 |
| 207 | discovery | 62 | 5 | negative | 1.741 | 1.0 | 0.275 |
| 208 | discovery | 2 | 0 | negative | 0.836 | 1.0 | 0.275 |
| 209 | discovery | 23 | 1 | negative | 0.535 | 6.0 | 0.162 |
| 210 | discovery | 31 | 2 | negative | 1.440 | 1.0 | 0.220 |
| 211 | discovery | 6 | 0 | positive | 1.138 | 1.0 | 0.220 |
| 212 | discovery | 18 | 1 | negative | 0.535 | 0.0 | 0.220 |
| 213 | discovery | 11 | 0 | negative | 2.948 | 1.0 | 0.183 |
| 214 | discovery | 43 | 3 | positive | -0.370 | 0.0 | 0.183 |
| 215 | discovery | 13 | 1 | positive | 0.836 | 3.0 | 0.220 |
| 216 | discovery | 21 | 1 | negative | -0.672 | 3.0 | 0.220 |
| 217 | discovery | 46 | 3 | negative | -0.069 | 1.0 | 0.263 |
| 218 | discovery | 91 | 7 | positive | 0.535 | 1.0 | 0.263 |
| 219 | discovery | 89 | 7 | negative | 0.836 | 1.0 | 0.263 |
| 220 | discovery | 70 | 5 | negative | -1.577 | 7.0 | 0.275 |
| 221 | discovery | 104 | 8 | negative | 1.741 | 7.0 | 0.275 |
| 222 | discovery | 5 | 0 | negative | 0.836 | 7.0 | 0.275 |
| 223 | discovery | 92 | 7 | negative | 0.233 | 1.0 | 0.263 |
| 224 | discovery | 20 | 1 | negative | 0.535 | 7.0 | 0.220 |
| 225 | discovery | 12 | 1 | negative | 1.440 | 7.0 | 0.220 |
| 226 | discovery | 7 | 0 | positive | 2.345 | 7.0 | 0.220 |
| 227 | discovery | 86 | 7 | negative | -0.672 | 0.0 | 0.263 |
| 228 | discovery | 10 | 0 | negative | 2.043 | 1.0 | 0.210 |
| 229 | discovery | 17 | 1 | negative | 1.440 | 0.0 | 0.233 |
| 230 | discovery | 48 | 4 | negative | 0.535 | 0.0 | 0.233 |
| 231 | discovery | 9 | 0 | negative | 1.138 | 1.0 | 0.191 |
| 232 | discovery | 45 | 3 | negative | -0.069 | 0.0 | 0.210 |
| 233 | discovery | 0 | 0 | negative | -0.069 | 1.0 | 0.191 |
| 234 | discovery | 16 | 1 | negative | 2.345 | 0.0 | 0.191 |
| 235 | discovery | 19 | 1 | negative | 1.138 | 0.0 | 0.191 |
| 236 | discovery | 1 | 0 | negative | -0.069 | 7.0 | 0.183 |
| 237 | discovery | 8 | 0 | negative | 1.138 | 7.0 | 0.183 |
| 238 | discovery | 40 | 3 | negative | 1.741 | 7.0 | 0.183 |
| 239 | discovery | 36 | 3 | positive | 1.440 | 7.0 | 0.183 |
| 240 | discovery | 39 | 3 | negative | 0.836 | 7.0 | 0.183 |
| 241 | discovery | 87 | 7 | negative | -0.370 | 3.0 | 0.210 |
| 242 | discovery | 37 | 3 | negative | 0.535 | 0.0 | 0.162 |
| 243 | discovery | 42 | 3 | negative | 0.836 | 0.0 | 0.162 |
| 244 | discovery | 98 | 8 | negative | -0.672 | 3.0 | 0.175 |
| 245 | discovery | 44 | 3 | negative | -0.672 | 0.0 | 0.162 |
| 246 | discovery | 93 | 7 | negative | 1.440 | 0.0 | 0.162 |
| 247 | discovery | 102 | 8 | negative | 1.138 | 0.0 | 0.162 |
| 248 | guard | 24 | 2 | negative | 0.233 | nan | nan |
| 249 | guard | 35 | 2 | negative | 0.535 | nan | nan |
| 250 | guard | 49 | 4 | negative | 0.535 | nan | nan |
| 251 | guard | 71 | 5 | negative | -0.672 | nan | nan |
| 252 | guard | 84 | 7 | negative | -0.974 | nan | nan |
| 253 | guard | 90 | 7 | negative | -0.069 | nan | nan |
| 254 | guard | 94 | 7 | negative | -0.370 | nan | nan |

## Case: dataset3_1200_2400 budget=20 seed=0

- event_recall_diff (core - nr): -0.167
- unique_bin_diff: -4
- repair_calls: 0

| idx | type | bin | chunk | label | prior | best_alt_chunk | best_alt_theta |
|---|---|---|---|---|---|---|---|
| 0 | audit | 118 | 9 | negative | 1.138 | 0.0 | 0.100 |
| 1 | audit | 116 | 9 | negative | 0.233 | 0.0 | 0.100 |
| 2 | discovery | 37 | 3 | negative | -0.069 | 0.0 | 0.100 |
| 3 | discovery | 60 | 5 | negative | -1.275 | 0.0 | 0.100 |
| 4 | discovery | 81 | 6 | negative | -0.672 | 0.0 | 0.100 |
| 5 | discovery | 14 | 1 | negative | -0.069 | 0.0 | 0.100 |
| 6 | discovery | 40 | 3 | negative | -0.370 | 0.0 | 0.100 |
| 7 | discovery | 71 | 5 | negative | -0.974 | 0.0 | 0.100 |
| 8 | discovery | 85 | 7 | negative | -0.672 | 0.0 | 0.100 |
| 9 | discovery | 55 | 4 | positive | 0.535 | 0.0 | 0.100 |
| 10 | discovery | 88 | 7 | negative | 0.233 | 4.0 | 0.550 |
| 11 | discovery | 50 | 4 | negative | 0.836 | 0.0 | 0.100 |
| 12 | discovery | 100 | 8 | negative | -0.974 | 4.0 | 0.367 |
| 13 | discovery | 74 | 6 | negative | -1.879 | 4.0 | 0.367 |
| 14 | discovery | 56 | 4 | positive | -0.069 | 0.0 | 0.100 |
| 15 | discovery | 35 | 2 | negative | 0.836 | 4.0 | 0.525 |
| 16 | discovery | 98 | 8 | negative | -0.974 | 4.0 | 0.525 |
| 17 | discovery | 54 | 4 | positive | -0.069 | 0.0 | 0.100 |
| 18 | discovery | 57 | 4 | positive | -0.974 | 0.0 | 0.100 |
| 19 | discovery | 59 | 4 | positive | -1.879 | 0.0 | 0.100 |
| 20 | discovery | 103 | 8 | negative | -1.577 | 0.0 | 0.100 |
| 21 | discovery | 92 | 7 | negative | -0.370 | 0.0 | 0.100 |
| 22 | discovery | 7 | 0 | negative | -0.672 | 1.0 | 0.100 |
| 23 | discovery | 107 | 8 | negative | -0.672 | 1.0 | 0.100 |
| 24 | discovery | 73 | 6 | negative | -1.879 | 1.0 | 0.100 |
| 25 | discovery | 13 | 1 | negative | -0.974 | 2.0 | 0.100 |
| 26 | discovery | 91 | 7 | negative | -0.370 | 2.0 | 0.100 |
| 27 | discovery | 83 | 6 | negative | 0.233 | 2.0 | 0.100 |

## Case: realcartest_2000_3200 budget=120 seed=0

- event_recall_diff (core - nr): -0.150
- unique_bin_diff: -3
- repair_calls: 11

| idx | type | bin | chunk | label | prior | best_alt_chunk | best_alt_theta |
|---|---|---|---|---|---|---|---|
| 0 | audit | 111 | 9 | positive | 0.410 | 0.0 | 0.100 |
| 1 | audit | 102 | 8 | negative | 0.482 | 9.0 | 0.550 |
| 2 | audit | 87 | 7 | positive | 0.497 | 9.0 | 0.550 |
| 3 | audit | 106 | 8 | positive | 0.380 | 7.0 | 0.550 |
| 4 | audit | 80 | 6 | negative | 0.379 | 7.0 | 0.550 |
| 5 | audit | 47 | 3 | negative | 0.203 | 7.0 | 0.550 |
| 6 | audit | 50 | 4 | positive | 0.431 | 7.0 | 0.550 |
| 7 | audit | 36 | 3 | negative | 0.469 | 4.0 | 0.550 |
| 8 | audit | 104 | 8 | negative | 0.444 | 4.0 | 0.550 |
| 9 | audit | 88 | 7 | positive | 0.515 | 4.0 | 0.550 |
| 10 | audit | 93 | 7 | negative | 0.475 | 4.0 | 0.550 |
| 11 | audit | 51 | 4 | negative | 0.469 | 9.0 | 0.550 |
| 12 | audit | 71 | 5 | positive | 0.425 | 9.0 | 0.550 |
| 13 | audit | 108 | 9 | negative | 0.340 | 5.0 | 0.550 |
| 14 | audit | 83 | 6 | positive | 0.349 | 5.0 | 0.550 |
| 15 | audit | 70 | 5 | positive | 0.361 | 7.0 | 0.525 |
| 16 | audit | 56 | 4 | positive | 0.386 | 5.0 | 0.700 |
| 17 | audit | 8 | 0 | negative | 0.281 | 5.0 | 0.700 |
| 18 | audit | 65 | 5 | negative | 0.311 | 4.0 | 0.525 |
| 19 | audit | 43 | 3 | negative | 0.213 | 4.0 | 0.525 |
| 20 | audit | 63 | 5 | negative | 0.296 | 4.0 | 0.525 |
| 21 | audit | 62 | 5 | negative | 0.290 | 4.0 | 0.525 |
| 22 | audit | 61 | 5 | negative | 0.274 | 4.0 | 0.525 |
| 23 | audit | 5 | 0 | positive | 0.352 | 4.0 | 0.525 |
| 24 | audit | 117 | 9 | negative | 0.351 | 4.0 | 0.525 |
| 25 | audit | 19 | 1 | negative | 0.167 | 4.0 | 0.525 |
| 26 | audit | 76 | 6 | positive | 0.397 | 4.0 | 0.525 |
| 27 | audit | 4 | 0 | positive | 0.277 | 4.0 | 0.525 |
| 28 | audit | 101 | 8 | negative | 0.233 | 0.0 | 0.525 |
| 29 | audit | 46 | 3 | negative | 0.183 | 0.0 | 0.525 |
| 30 | repair | 75 | 6 | negative | 0.314 | 0.0 | 0.525 |
| 31 | repair | 77 | 6 | positive | 0.343 | 0.0 | 0.525 |
| 32 | repair | 55 | 4 | negative | 0.392 | 0.0 | 0.525 |
| 33 | repair | 57 | 4 | negative | 0.315 | 0.0 | 0.525 |
| 34 | repair | 105 | 8 | negative | 0.521 | 0.0 | 0.525 |
| 35 | repair | 107 | 8 | negative | 0.449 | 0.0 | 0.525 |
| 36 | repair | 69 | 5 | negative | 0.316 | 0.0 | 0.525 |
| 37 | repair | 6 | 0 | negative | 0.267 | 7.0 | 0.525 |
| 38 | repair | 82 | 6 | negative | 0.426 | 7.0 | 0.525 |
| 39 | repair | 84 | 7 | positive | 0.428 | 6.0 | 0.443 |
| 40 | repair | 3 | 0 | positive | 0.321 | 7.0 | 0.620 |
| 41 | discovery | 112 | 9 | negative | 0.335 | 0.0 | 0.100 |
| 42 | discovery | 22 | 1 | negative | 0.128 | 0.0 | 0.100 |
| 43 | discovery | 87 | 7 | positive | 0.497 | 0.0 | 0.100 |
| 44 | discovery | 90 | 7 | negative | 0.266 | 0.0 | 0.100 |
| 45 | discovery | 86 | 7 | positive | 0.480 | 0.0 | 0.100 |
| 46 | discovery | 106 | 8 | positive | 0.380 | 7.0 | 0.525 |
| 47 | discovery | 94 | 7 | negative | 0.257 | 8.0 | 0.550 |
| 48 | discovery | 89 | 7 | negative | 0.323 | 8.0 | 0.550 |
| 49 | discovery | 101 | 8 | negative | 0.233 | 7.0 | 0.350 |
| 50 | discovery | 84 | 7 | positive | 0.428 | 8.0 | 0.367 |
| 51 | discovery | 100 | 8 | negative | 0.323 | 7.0 | 0.443 |
| 52 | discovery | 60 | 5 | negative | 0.315 | 7.0 | 0.443 |
| 53 | discovery | 78 | 6 | negative | 0.331 | 7.0 | 0.443 |
| 54 | discovery | 85 | 7 | positive | 0.458 | 8.0 | 0.275 |
| 55 | discovery | 56 | 4 | positive | 0.386 | 7.0 | 0.512 |
| 56 | discovery | 95 | 7 | negative | 0.393 | 4.0 | 0.550 |
| 57 | discovery | 0 | 0 | negative | 0.400 | 4.0 | 0.550 |
| 58 | discovery | 50 | 4 | positive | 0.431 | 7.0 | 0.456 |
| 59 | discovery | 24 | 2 | negative | 0.192 | 4.0 | 0.700 |
| 60 | discovery | 92 | 7 | negative | 0.451 | 4.0 | 0.700 |
| 61 | discovery | 36 | 3 | negative | 0.469 | 4.0 | 0.700 |
| 62 | discovery | 72 | 6 | negative | 0.333 | 4.0 | 0.700 |
| 63 | discovery | 58 | 4 | positive | 0.287 | 7.0 | 0.410 |
| 64 | discovery | 54 | 4 | negative | 0.330 | 7.0 | 0.410 |
| 65 | discovery | 49 | 4 | positive | 0.474 | 7.0 | 0.410 |
| 66 | discovery | 57 | 4 | negative | 0.315 | 7.0 | 0.410 |
| 67 | discovery | 48 | 4 | negative | 0.250 | 7.0 | 0.410 |
| 68 | discovery | 20 | 1 | negative | 0.150 | 4.0 | 0.512 |
| 69 | discovery | 103 | 8 | negative | 0.467 | 4.0 | 0.512 |
| 70 | discovery | 4 | 0 | positive | 0.277 | 4.0 | 0.512 |
| 71 | discovery | 52 | 4 | negative | 0.287 | 7.0 | 0.410 |
| 72 | discovery | 8 | 0 | negative | 0.281 | 4.0 | 0.456 |
| 73 | discovery | 51 | 4 | negative | 0.469 | 7.0 | 0.410 |
| 74 | discovery | 93 | 7 | negative | 0.475 | 4.0 | 0.410 |
| 75 | discovery | 42 | 3 | negative | 0.202 | 4.0 | 0.410 |
| 76 | discovery | 88 | 7 | positive | 0.515 | 4.0 | 0.410 |
| 77 | discovery | 91 | 7 | negative | 0.356 | 4.0 | 0.410 |
| 78 | discovery | 53 | 4 | positive | 0.245 | 7.0 | 0.392 |
| 79 | discovery | 55 | 4 | negative | 0.392 | 7.0 | 0.392 |
| 80 | discovery | 59 | 4 | negative | 0.369 | 7.0 | 0.392 |
| 81 | discovery | 11 | 0 | negative | 0.227 | 4.0 | 0.392 |
| 82 | discovery | 9 | 0 | positive | 0.292 | 4.0 | 0.392 |
| 83 | discovery | 7 | 0 | positive | 0.244 | 4.0 | 0.392 |
| 84 | discovery | 96 | 8 | positive | 0.241 | 0.0 | 0.443 |
| 85 | discovery | 75 | 6 | negative | 0.314 | 0.0 | 0.443 |
| 86 | discovery | 6 | 0 | negative | 0.267 | 4.0 | 0.392 |
| 87 | discovery | 33 | 2 | negative | 0.354 | 4.0 | 0.392 |
| 88 | discovery | 10 | 0 | negative | 0.347 | 4.0 | 0.392 |
| 89 | discovery | 2 | 0 | negative | 0.218 | 4.0 | 0.392 |
| 90 | discovery | 3 | 0 | positive | 0.321 | 4.0 | 0.392 |
| 91 | discovery | 1 | 0 | negative | 0.186 | 4.0 | 0.392 |
| 92 | discovery | 105 | 8 | negative | 0.521 | 4.0 | 0.392 |
| 93 | discovery | 99 | 8 | negative | 0.391 | 4.0 | 0.392 |
| 94 | discovery | 98 | 8 | positive | 0.389 | 4.0 | 0.392 |
| 95 | discovery | 5 | 0 | positive | 0.352 | 4.0 | 0.392 |
| 96 | discovery | 102 | 8 | negative | 0.482 | 0.0 | 0.392 |
| 97 | discovery | 107 | 8 | negative | 0.449 | 0.0 | 0.392 |
| 98 | discovery | 97 | 8 | negative | 0.320 | 0.0 | 0.392 |
| 99 | discovery | 104 | 8 | negative | 0.444 | 0.0 | 0.392 |
| 100 | discovery | 83 | 6 | positive | 0.349 | 0.0 | 0.392 |
| 101 | discovery | 12 | 1 | positive | 0.351 | 0.0 | 0.392 |
| 102 | discovery | 19 | 1 | negative | 0.167 | 0.0 | 0.392 |
| 103 | discovery | 17 | 1 | negative | 0.184 | 0.0 | 0.392 |
| 104 | discovery | 14 | 1 | negative | 0.113 | 0.0 | 0.392 |
| 105 | discovery | 115 | 9 | negative | 0.281 | 0.0 | 0.392 |
| 106 | discovery | 82 | 6 | negative | 0.426 | 0.0 | 0.392 |
| 107 | discovery | 73 | 6 | negative | 0.406 | 0.0 | 0.392 |
| 108 | discovery | 79 | 6 | positive | 0.411 | 0.0 | 0.392 |
| 109 | discovery | 77 | 6 | positive | 0.343 | 0.0 | 0.392 |
| 110 | discovery | 74 | 6 | negative | 0.205 | 0.0 | 0.392 |
| 111 | discovery | 81 | 6 | positive | 0.472 | 0.0 | 0.392 |
| 112 | discovery | 80 | 6 | negative | 0.379 | 0.0 | 0.392 |
| 113 | discovery | 21 | 1 | negative | 0.108 | 0.0 | 0.392 |
| 114 | discovery | 76 | 6 | positive | 0.397 | 0.0 | 0.392 |
| 115 | discovery | 46 | 3 | negative | 0.183 | 0.0 | 0.392 |
| 116 | discovery | 18 | 1 | negative | 0.167 | 0.0 | 0.392 |
| 117 | discovery | 110 | 9 | negative | 0.186 | 0.0 | 0.392 |
| 118 | discovery | 15 | 1 | negative | 0.216 | 0.0 | 0.392 |
| 119 | discovery | 16 | 1 | negative | 0.336 | 0.0 | 0.392 |
| 120 | discovery | 72 | 6 | negative | 0.333 | 0.0 | 0.100 |
| 121 | discovery | 18 | 1 | negative | 0.167 | 0.0 | 0.100 |
| 122 | discovery | 112 | 9 | negative | 0.335 | 0.0 | 0.100 |
| 123 | discovery | 30 | 2 | negative | 0.111 | 0.0 | 0.100 |
| 124 | discovery | 68 | 5 | negative | 0.405 | 0.0 | 0.100 |
| 125 | discovery | 5 | 0 | positive | 0.352 | 3.0 | 0.100 |
| 126 | discovery | 3 | 0 | positive | 0.321 | 3.0 | 0.100 |
| 127 | discovery | 9 | 0 | positive | 0.292 | 3.0 | 0.100 |
| 128 | discovery | 11 | 0 | negative | 0.227 | 3.0 | 0.100 |
| 129 | discovery | 51 | 4 | negative | 0.469 | 0.0 | 0.620 |
| 130 | discovery | 0 | 0 | negative | 0.400 | 3.0 | 0.100 |
| 131 | discovery | 46 | 3 | negative | 0.183 | 0.0 | 0.517 |
| 132 | discovery | 1 | 0 | negative | 0.186 | 7.0 | 0.100 |
| 133 | discovery | 6 | 0 | negative | 0.267 | 7.0 | 0.100 |
| 134 | discovery | 4 | 0 | positive | 0.277 | 7.0 | 0.100 |
| 135 | discovery | 10 | 0 | negative | 0.347 | 7.0 | 0.100 |
| 136 | discovery | 2 | 0 | negative | 0.218 | 7.0 | 0.100 |
| 137 | discovery | 100 | 8 | negative | 0.323 | 0.0 | 0.373 |
| 138 | discovery | 32 | 2 | positive | 0.218 | 0.0 | 0.373 |
| 139 | discovery | 7 | 0 | positive | 0.244 | 2.0 | 0.367 |
| 140 | discovery | 74 | 6 | negative | 0.205 | 0.0 | 0.425 |
| 141 | discovery | 8 | 0 | negative | 0.281 | 2.0 | 0.367 |
| 142 | discovery | 33 | 2 | negative | 0.354 | 0.0 | 0.392 |
| 143 | discovery | 20 | 1 | negative | 0.150 | 0.0 | 0.392 |
| 144 | discovery | 64 | 5 | negative | 0.299 | 0.0 | 0.392 |
| 145 | discovery | 38 | 3 | positive | 0.261 | 0.0 | 0.392 |
| 146 | discovery | 55 | 4 | negative | 0.392 | 0.0 | 0.392 |
| 147 | discovery | 22 | 1 | negative | 0.128 | 0.0 | 0.392 |
| 148 | discovery | 28 | 2 | negative | 0.335 | 0.0 | 0.392 |
| 149 | discovery | 27 | 2 | negative | 0.388 | 0.0 | 0.392 |
| 150 | discovery | 44 | 3 | negative | 0.187 | 0.0 | 0.392 |
| 151 | discovery | 25 | 2 | positive | 0.246 | 0.0 | 0.392 |
| 152 | discovery | 35 | 2 | negative | 0.206 | 0.0 | 0.392 |
| 153 | discovery | 87 | 7 | positive | 0.497 | 0.0 | 0.392 |
| 154 | discovery | 58 | 4 | positive | 0.287 | 7.0 | 0.550 |
| 155 | discovery | 90 | 7 | negative | 0.266 | 0.0 | 0.392 |
| 156 | discovery | 42 | 3 | negative | 0.202 | 0.0 | 0.392 |
| 157 | discovery | 91 | 7 | negative | 0.356 | 0.0 | 0.392 |
| 158 | discovery | 59 | 4 | negative | 0.369 | 0.0 | 0.392 |
| 159 | discovery | 31 | 2 | negative | 0.175 | 0.0 | 0.392 |
| 160 | discovery | 88 | 7 | positive | 0.515 | 0.0 | 0.392 |
| 161 | discovery | 94 | 7 | negative | 0.257 | 0.0 | 0.392 |
| 162 | discovery | 48 | 4 | negative | 0.250 | 0.0 | 0.392 |
| 163 | discovery | 95 | 7 | negative | 0.393 | 0.0 | 0.392 |
| 164 | discovery | 45 | 3 | negative | 0.180 | 0.0 | 0.392 |
| 165 | discovery | 93 | 7 | negative | 0.475 | 0.0 | 0.392 |
| 166 | discovery | 92 | 7 | negative | 0.451 | 0.0 | 0.392 |
| 167 | discovery | 41 | 3 | negative | 0.250 | 0.0 | 0.392 |
| 168 | discovery | 34 | 2 | negative | 0.280 | 0.0 | 0.392 |
| 169 | discovery | 52 | 4 | negative | 0.287 | 0.0 | 0.392 |
| 170 | discovery | 49 | 4 | positive | 0.474 | 0.0 | 0.392 |
| 171 | discovery | 85 | 7 | positive | 0.458 | 0.0 | 0.392 |
| 172 | discovery | 29 | 2 | negative | 0.158 | 0.0 | 0.392 |
| 173 | discovery | 50 | 4 | positive | 0.431 | 0.0 | 0.392 |
| 174 | discovery | 89 | 7 | negative | 0.323 | 0.0 | 0.392 |
| 175 | discovery | 54 | 4 | negative | 0.330 | 0.0 | 0.392 |
| 176 | discovery | 86 | 7 | positive | 0.480 | 0.0 | 0.392 |
| 177 | discovery | 26 | 2 | negative | 0.288 | 0.0 | 0.392 |
| 178 | discovery | 84 | 7 | positive | 0.428 | 0.0 | 0.392 |
| 179 | discovery | 53 | 4 | positive | 0.245 | 0.0 | 0.392 |
| 180 | discovery | 56 | 4 | positive | 0.386 | 0.0 | 0.392 |
| 181 | discovery | 57 | 4 | negative | 0.315 | 0.0 | 0.392 |
| 182 | discovery | 39 | 3 | positive | 0.350 | 0.0 | 0.392 |
| 183 | discovery | 106 | 8 | positive | 0.380 | 0.0 | 0.392 |
| 184 | discovery | 24 | 2 | negative | 0.192 | 0.0 | 0.392 |
| 185 | discovery | 107 | 8 | negative | 0.449 | 0.0 | 0.392 |
| 186 | discovery | 47 | 3 | negative | 0.203 | 0.0 | 0.392 |
| 187 | discovery | 36 | 3 | negative | 0.469 | 0.0 | 0.392 |
| 188 | discovery | 37 | 3 | negative | 0.271 | 0.0 | 0.392 |
| 189 | discovery | 43 | 3 | negative | 0.213 | 0.0 | 0.392 |
| 190 | discovery | 96 | 8 | positive | 0.241 | 0.0 | 0.392 |
| 191 | discovery | 104 | 8 | negative | 0.444 | 0.0 | 0.392 |
| 192 | discovery | 35 | 2 | negative | 0.206 | 0.0 | 0.100 |
| 193 | discovery | 82 | 6 | negative | 0.426 | 0.0 | 0.100 |
| 194 | discovery | 12 | 1 | positive | 0.351 | 0.0 | 0.100 |
| 195 | discovery | 23 | 1 | negative | 0.191 | 0.0 | 0.100 |
| 196 | discovery | 13 | 1 | negative | 0.174 | 0.0 | 0.100 |
| 197 | discovery | 3 | 0 | positive | 0.321 | 1.0 | 0.275 |
| 198 | discovery | 10 | 0 | negative | 0.347 | 1.0 | 0.275 |
| 199 | discovery | 1 | 0 | negative | 0.186 | 1.0 | 0.275 |
| 200 | discovery | 74 | 6 | negative | 0.205 | 0.0 | 0.275 |
| 201 | discovery | 46 | 3 | negative | 0.183 | 0.0 | 0.275 |
| 202 | discovery | 55 | 4 | negative | 0.392 | 0.0 | 0.275 |
| 203 | discovery | 0 | 0 | negative | 0.400 | 1.0 | 0.275 |
| 204 | discovery | 65 | 5 | negative | 0.311 | 1.0 | 0.275 |
| 205 | discovery | 70 | 5 | positive | 0.361 | 1.0 | 0.275 |
| 206 | discovery | 68 | 5 | negative | 0.405 | 1.0 | 0.275 |
| 207 | discovery | 19 | 1 | negative | 0.167 | 5.0 | 0.275 |
| 208 | discovery | 6 | 0 | negative | 0.267 | 5.0 | 0.275 |
| 209 | discovery | 96 | 8 | positive | 0.241 | 5.0 | 0.275 |
| 210 | discovery | 105 | 8 | negative | 0.521 | 5.0 | 0.275 |
| 211 | discovery | 115 | 9 | negative | 0.281 | 8.0 | 0.367 |
| 212 | discovery | 11 | 0 | negative | 0.227 | 8.0 | 0.367 |
| 213 | discovery | 69 | 5 | negative | 0.316 | 8.0 | 0.367 |
| 214 | discovery | 71 | 5 | positive | 0.425 | 8.0 | 0.367 |
| 215 | discovery | 85 | 7 | positive | 0.458 | 8.0 | 0.367 |
| 216 | discovery | 62 | 5 | negative | 0.290 | 7.0 | 0.550 |
| 217 | discovery | 4 | 0 | positive | 0.277 | 7.0 | 0.550 |
| 218 | discovery | 88 | 7 | positive | 0.515 | 8.0 | 0.367 |
| 219 | discovery | 91 | 7 | negative | 0.356 | 8.0 | 0.367 |
| 220 | discovery | 33 | 2 | negative | 0.354 | 7.0 | 0.525 |
| 221 | discovery | 95 | 7 | negative | 0.393 | 8.0 | 0.367 |
| 222 | discovery | 98 | 8 | positive | 0.389 | 7.0 | 0.420 |
| 223 | discovery | 107 | 8 | negative | 0.449 | 7.0 | 0.420 |
| 224 | discovery | 90 | 7 | negative | 0.266 | 8.0 | 0.420 |
| 225 | discovery | 89 | 7 | negative | 0.323 | 8.0 | 0.420 |
| 226 | discovery | 9 | 0 | positive | 0.292 | 8.0 | 0.420 |
| 227 | discovery | 2 | 0 | negative | 0.218 | 8.0 | 0.420 |
| 228 | discovery | 99 | 8 | negative | 0.391 | 0.0 | 0.310 |
| 229 | discovery | 7 | 0 | positive | 0.244 | 8.0 | 0.350 |
| 230 | discovery | 94 | 7 | negative | 0.257 | 0.0 | 0.373 |
| 231 | discovery | 59 | 4 | negative | 0.369 | 0.0 | 0.373 |
| 232 | discovery | 100 | 8 | negative | 0.323 | 0.0 | 0.373 |
| 233 | discovery | 84 | 7 | positive | 0.428 | 0.0 | 0.373 |
| 234 | discovery | 119 | 9 | negative | 0.243 | 0.0 | 0.373 |
| 235 | discovery | 21 | 1 | negative | 0.108 | 0.0 | 0.373 |
| 236 | discovery | 63 | 5 | negative | 0.296 | 0.0 | 0.373 |
| 237 | discovery | 102 | 8 | negative | 0.482 | 0.0 | 0.373 |
| 238 | discovery | 5 | 0 | positive | 0.352 | 7.0 | 0.344 |
| 239 | discovery | 106 | 8 | positive | 0.380 | 0.0 | 0.425 |
| 240 | discovery | 8 | 0 | negative | 0.281 | 7.0 | 0.344 |
| 241 | discovery | 92 | 7 | negative | 0.451 | 0.0 | 0.392 |
| 242 | discovery | 67 | 5 | negative | 0.334 | 0.0 | 0.392 |
| 243 | discovery | 60 | 5 | negative | 0.315 | 0.0 | 0.392 |
| 244 | discovery | 61 | 5 | negative | 0.274 | 0.0 | 0.392 |
| 245 | discovery | 93 | 7 | negative | 0.475 | 0.0 | 0.392 |
| 246 | discovery | 101 | 8 | negative | 0.233 | 0.0 | 0.392 |
| 247 | discovery | 104 | 8 | negative | 0.444 | 0.0 | 0.392 |
| 248 | discovery | 97 | 8 | negative | 0.320 | 0.0 | 0.392 |
| 249 | discovery | 37 | 3 | negative | 0.271 | 0.0 | 0.392 |
| 250 | discovery | 18 | 1 | negative | 0.167 | 0.0 | 0.392 |
| 251 | discovery | 97 | 8 | negative | 0.320 | 0.0 | 0.100 |
| 252 | discovery | 119 | 9 | negative | 0.243 | 0.0 | 0.100 |
| 253 | discovery | 59 | 4 | negative | 0.369 | 0.0 | 0.100 |
| 254 | discovery | 79 | 6 | positive | 0.411 | 0.0 | 0.100 |
| 255 | discovery | 76 | 6 | positive | 0.397 | 0.0 | 0.100 |
| 256 | discovery | 87 | 7 | positive | 0.497 | 6.0 | 0.700 |
| 257 | discovery | 37 | 3 | negative | 0.271 | 6.0 | 0.700 |
| 258 | discovery | 63 | 5 | negative | 0.296 | 6.0 | 0.700 |
| 259 | discovery | 85 | 7 | positive | 0.458 | 6.0 | 0.700 |
| 260 | discovery | 84 | 7 | positive | 0.428 | 6.0 | 0.700 |
| 261 | discovery | 35 | 2 | negative | 0.206 | 7.0 | 0.775 |
| 262 | discovery | 94 | 7 | negative | 0.257 | 6.0 | 0.700 |
| 263 | discovery | 77 | 6 | positive | 0.343 | 7.0 | 0.620 |
| 264 | discovery | 74 | 6 | negative | 0.205 | 7.0 | 0.620 |
| 265 | discovery | 90 | 7 | negative | 0.266 | 6.0 | 0.620 |
| 266 | discovery | 95 | 7 | negative | 0.393 | 6.0 | 0.620 |
| 267 | discovery | 78 | 6 | negative | 0.331 | 7.0 | 0.443 |
| 268 | discovery | 7 | 0 | positive | 0.244 | 6.0 | 0.517 |
| 269 | discovery | 88 | 7 | positive | 0.515 | 0.0 | 0.550 |
| 270 | discovery | 113 | 9 | negative | 0.249 | 0.0 | 0.550 |
| 271 | discovery | 45 | 3 | negative | 0.180 | 0.0 | 0.550 |
| 272 | discovery | 11 | 0 | negative | 0.227 | 6.0 | 0.517 |
| 273 | discovery | 26 | 2 | negative | 0.288 | 6.0 | 0.517 |
| 274 | discovery | 92 | 7 | negative | 0.451 | 6.0 | 0.517 |
| 275 | discovery | 81 | 6 | positive | 0.472 | 7.0 | 0.456 |
| 276 | discovery | 82 | 6 | negative | 0.426 | 7.0 | 0.456 |
| 277 | discovery | 80 | 6 | negative | 0.379 | 7.0 | 0.456 |
| 278 | discovery | 89 | 7 | negative | 0.323 | 6.0 | 0.456 |
| 279 | discovery | 73 | 6 | negative | 0.406 | 7.0 | 0.410 |
| 280 | discovery | 83 | 6 | positive | 0.349 | 7.0 | 0.410 |
| 281 | discovery | 75 | 6 | negative | 0.314 | 7.0 | 0.410 |
| 282 | discovery | 91 | 7 | negative | 0.356 | 6.0 | 0.425 |
| 283 | discovery | 72 | 6 | negative | 0.333 | 7.0 | 0.373 |
| 284 | discovery | 114 | 9 | negative | 0.169 | 6.0 | 0.392 |
| 285 | discovery | 86 | 7 | positive | 0.480 | 6.0 | 0.392 |
| 286 | discovery | 68 | 5 | negative | 0.405 | 7.0 | 0.425 |
| 287 | discovery | 0 | 0 | negative | 0.400 | 7.0 | 0.425 |
| 288 | discovery | 1 | 0 | negative | 0.186 | 7.0 | 0.425 |
| 289 | discovery | 14 | 1 | negative | 0.113 | 7.0 | 0.425 |
| 290 | discovery | 93 | 7 | negative | 0.475 | 6.0 | 0.392 |
| 291 | discovery | 39 | 3 | positive | 0.350 | 6.0 | 0.392 |
| 292 | discovery | 3 | 0 | positive | 0.321 | 6.0 | 0.392 |
| 293 | discovery | 9 | 0 | positive | 0.292 | 6.0 | 0.392 |
| 294 | discovery | 10 | 0 | negative | 0.347 | 6.0 | 0.392 |
| 295 | discovery | 40 | 3 | positive | 0.235 | 6.0 | 0.392 |
| 296 | discovery | 38 | 3 | positive | 0.261 | 6.0 | 0.392 |
| 297 | discovery | 42 | 3 | negative | 0.202 | 6.0 | 0.392 |
| 298 | discovery | 46 | 3 | negative | 0.183 | 6.0 | 0.392 |
| 299 | discovery | 43 | 3 | negative | 0.213 | 6.0 | 0.392 |
| 300 | discovery | 4 | 0 | positive | 0.277 | 6.0 | 0.392 |
| 301 | discovery | 54 | 4 | negative | 0.330 | 0.0 | 0.456 |
| 302 | discovery | 8 | 0 | negative | 0.281 | 6.0 | 0.392 |
| 303 | discovery | 2 | 0 | negative | 0.218 | 6.0 | 0.392 |
| 304 | discovery | 6 | 0 | negative | 0.267 | 6.0 | 0.392 |
| 305 | discovery | 5 | 0 | positive | 0.352 | 6.0 | 0.392 |
| 306 | guard | 67 | 5 | negative | 0.334 | nan | nan |
| 307 | guard | 96 | 8 | positive | 0.241 | nan | nan |
| 308 | guard | 97 | 8 | negative | 0.320 | nan | nan |
| 309 | guard | 12 | 1 | positive | 0.351 | nan | nan |
| 310 | guard | 13 | 1 | negative | 0.174 | nan | nan |
| 311 | guard | 34 | 2 | negative | 0.280 | nan | nan |
| 312 | guard | 41 | 3 | negative | 0.250 | nan | nan |
| 313 | guard | 103 | 8 | negative | 0.467 | nan | nan |
| 314 | guard | 109 | 9 | negative | 0.267 | nan | nan |
| 315 | guard | 53 | 4 | positive | 0.245 | nan | nan |
| 316 | guard | 52 | 4 | negative | 0.287 | nan | nan |
| 317 | guard | 58 | 4 | positive | 0.287 | nan | nan |
| 318 | guard | 59 | 4 | negative | 0.369 | nan | nan |
| 319 | guard | 49 | 4 | positive | 0.474 | nan | nan |
| 320 | guard | 48 | 4 | negative | 0.250 | nan | nan |
| 321 | guard | 52 | 4 | negative | 0.287 | nan | nan |
| 322 | guard | 110 | 9 | negative | 0.186 | nan | nan |
| 323 | guard | 112 | 9 | negative | 0.335 | nan | nan |

## Case: realcartest_3200_3830 budget=63 seed=0

- event_recall_diff (core - nr): -0.143
- unique_bin_diff: -6
- repair_calls: 2

| idx | type | bin | chunk | label | prior | best_alt_chunk | best_alt_theta |
|---|---|---|---|---|---|---|---|
| 0 | audit | 58 | 4 | positive | 1.000 | 0.0 | 0.100 |
| 1 | audit | 29 | 2 | negative | 1.000 | 4.0 | 0.550 |
| 2 | audit | 24 | 2 | negative | 1.000 | 4.0 | 0.550 |
| 3 | audit | 56 | 4 | negative | 0.431 | 0.0 | 0.100 |
| 4 | audit | 48 | 4 | positive | 0.563 | 0.0 | 0.100 |
| 5 | audit | 30 | 2 | negative | 0.637 | 4.0 | 0.525 |
| 6 | audit | 2 | 0 | positive | 1.000 | 4.0 | 0.525 |
| 7 | audit | 1 | 0 | positive | 1.000 | 4.0 | 0.525 |
| 8 | audit | 39 | 3 | negative | 1.000 | 0.0 | 0.700 |
| 9 | audit | 44 | 3 | negative | 0.368 | 0.0 | 0.700 |
| 10 | audit | 9 | 0 | negative | 0.906 | 4.0 | 0.525 |
| 11 | audit | 50 | 4 | negative | 0.895 | 0.0 | 0.525 |
| 12 | audit | 16 | 1 | positive | 0.966 | 0.0 | 0.525 |
| 13 | audit | 15 | 1 | negative | 0.621 | 0.0 | 0.525 |
| 14 | audit | 57 | 4 | negative | 0.788 | 0.0 | 0.525 |
| 15 | audit | 49 | 4 | positive | 0.759 | 0.0 | 0.525 |
| 16 | repair | 17 | 1 | positive | 0.966 | 0.0 | 0.525 |
| 17 | repair | 47 | 3 | negative | 0.446 | 0.0 | 0.525 |
| 18 | discovery | 6 | 0 | negative | 1.000 | 1.0 | 0.100 |
| 19 | discovery | 35 | 2 | negative | 0.892 | 1.0 | 0.100 |
| 20 | discovery | 46 | 3 | negative | 0.446 | 1.0 | 0.100 |
| 21 | discovery | 22 | 1 | negative | 0.716 | 4.0 | 0.100 |
| 22 | discovery | 9 | 0 | negative | 0.906 | 4.0 | 0.100 |
| 23 | discovery | 4 | 0 | negative | 1.000 | 4.0 | 0.100 |
| 24 | discovery | 32 | 2 | negative | 0.815 | 4.0 | 0.100 |
| 25 | discovery | 60 | 5 | negative | 0.512 | 4.0 | 0.100 |
| 26 | discovery | 7 | 0 | negative | 1.000 | 4.0 | 0.100 |
| 27 | discovery | 41 | 3 | negative | 0.421 | 4.0 | 0.100 |
| 28 | discovery | 39 | 3 | negative | 1.000 | 4.0 | 0.100 |
| 29 | discovery | 44 | 3 | negative | 0.368 | 4.0 | 0.100 |
| 30 | discovery | 61 | 5 | negative | 0.729 | 4.0 | 0.100 |
| 31 | discovery | 18 | 1 | negative | 0.870 | 4.0 | 0.100 |
| 32 | discovery | 40 | 3 | negative | 1.000 | 4.0 | 0.100 |
| 33 | discovery | 26 | 2 | negative | 0.829 | 4.0 | 0.100 |
| 34 | discovery | 24 | 2 | negative | 1.000 | 4.0 | 0.100 |
| 35 | discovery | 53 | 4 | negative | 0.706 | 1.0 | 0.033 |
| 36 | discovery | 14 | 1 | negative | 0.621 | 4.0 | 0.050 |
| 37 | discovery | 38 | 3 | negative | 0.873 | 4.0 | 0.050 |
| 38 | discovery | 20 | 1 | negative | 0.661 | 4.0 | 0.050 |
| 39 | discovery | 62 | 5 | negative | 0.729 | 4.0 | 0.050 |
| 40 | discovery | 58 | 4 | positive | 1.000 | 5.0 | 0.025 |
| 41 | discovery | 51 | 4 | positive | 0.895 | 5.0 | 0.025 |
| 42 | discovery | 49 | 4 | positive | 0.759 | 5.0 | 0.025 |
| 43 | discovery | 48 | 4 | positive | 0.563 | 5.0 | 0.025 |
| 44 | discovery | 55 | 4 | negative | 0.437 | 5.0 | 0.025 |
| 45 | discovery | 56 | 4 | negative | 0.431 | 5.0 | 0.025 |
| 46 | discovery | 59 | 4 | negative | 1.000 | 5.0 | 0.025 |
| 47 | discovery | 50 | 4 | negative | 0.895 | 5.0 | 0.025 |
| 48 | discovery | 57 | 4 | negative | 0.788 | 5.0 | 0.025 |
| 49 | discovery | 52 | 4 | positive | 0.708 | 5.0 | 0.025 |
| 50 | discovery | 54 | 4 | negative | 0.526 | 5.0 | 0.025 |
| 51 | discovery | 13 | 1 | negative | 0.680 | 4.0 | 0.392 |
| 52 | discovery | 42 | 3 | negative | 0.522 | 4.0 | 0.392 |
| 53 | discovery | 16 | 1 | positive | 0.966 | 4.0 | 0.392 |
| 54 | discovery | 12 | 1 | negative | 0.463 | 4.0 | 0.392 |
| 55 | discovery | 47 | 3 | negative | 0.446 | 4.0 | 0.392 |
| 56 | discovery | 21 | 1 | negative | 0.716 | 4.0 | 0.392 |
| 57 | discovery | 23 | 1 | negative | 0.251 | 4.0 | 0.392 |
| 58 | discovery | 17 | 1 | positive | 0.966 | 4.0 | 0.392 |
| 59 | discovery | 15 | 1 | negative | 0.621 | 4.0 | 0.392 |
| 60 | discovery | 19 | 1 | negative | 0.244 | 4.0 | 0.392 |
| 61 | discovery | 43 | 3 | negative | 0.522 | 4.0 | 0.392 |
| 62 | discovery | 36 | 3 | negative | 0.901 | 4.0 | 0.392 |
| 63 | discovery | 13 | 1 | negative | 0.680 | 0.0 | 0.100 |
| 64 | discovery | 43 | 3 | negative | 0.522 | 0.0 | 0.100 |
| 65 | discovery | 26 | 2 | negative | 0.829 | 0.0 | 0.100 |
| 66 | discovery | 30 | 2 | negative | 0.637 | 0.0 | 0.100 |
| 67 | discovery | 34 | 2 | negative | 0.861 | 0.0 | 0.100 |
| 68 | discovery | 61 | 5 | negative | 0.729 | 0.0 | 0.100 |
| 69 | discovery | 48 | 4 | positive | 0.563 | 0.0 | 0.100 |
| 70 | discovery | 57 | 4 | negative | 0.788 | 0.0 | 0.100 |
| 71 | discovery | 59 | 4 | negative | 1.000 | 0.0 | 0.100 |
| 72 | discovery | 0 | 0 | positive | 0.914 | 4.0 | 0.275 |
| 73 | discovery | 56 | 4 | negative | 0.431 | 0.0 | 0.550 |
| 74 | discovery | 23 | 1 | negative | 0.251 | 0.0 | 0.550 |
| 75 | discovery | 4 | 0 | negative | 1.000 | 4.0 | 0.220 |
| 76 | discovery | 8 | 0 | negative | 0.671 | 4.0 | 0.220 |
| 77 | discovery | 3 | 0 | positive | 1.000 | 4.0 | 0.220 |
| 78 | discovery | 1 | 0 | positive | 1.000 | 4.0 | 0.220 |
| 79 | discovery | 7 | 0 | negative | 1.000 | 4.0 | 0.220 |
| 80 | discovery | 41 | 3 | negative | 0.421 | 0.0 | 0.443 |
| 81 | discovery | 6 | 0 | negative | 1.000 | 4.0 | 0.220 |
| 82 | discovery | 2 | 0 | positive | 1.000 | 4.0 | 0.220 |
| 83 | discovery | 9 | 0 | negative | 0.906 | 4.0 | 0.220 |
| 84 | discovery | 11 | 0 | negative | 0.783 | 4.0 | 0.220 |
| 85 | discovery | 54 | 4 | negative | 0.526 | 0.0 | 0.373 |
| 86 | discovery | 10 | 0 | negative | 0.817 | 4.0 | 0.183 |
| 87 | discovery | 5 | 0 | negative | 1.000 | 4.0 | 0.183 |
| 88 | discovery | 44 | 3 | negative | 0.368 | 0.0 | 0.315 |
| 89 | discovery | 51 | 4 | positive | 0.895 | 0.0 | 0.315 |
| 90 | discovery | 49 | 4 | positive | 0.759 | 0.0 | 0.315 |
| 91 | discovery | 58 | 4 | positive | 1.000 | 0.0 | 0.315 |
| 92 | discovery | 55 | 4 | negative | 0.437 | 0.0 | 0.315 |
| 93 | discovery | 50 | 4 | negative | 0.895 | 0.0 | 0.315 |
| 94 | discovery | 52 | 4 | positive | 0.708 | 0.0 | 0.315 |
| 95 | discovery | 53 | 4 | negative | 0.706 | 0.0 | 0.315 |
| 96 | discovery | 15 | 1 | negative | 0.621 | 4.0 | 0.392 |
| 97 | discovery | 62 | 5 | negative | 0.729 | 4.0 | 0.392 |
| 98 | discovery | 24 | 2 | negative | 1.000 | 4.0 | 0.392 |
| 99 | discovery | 60 | 5 | negative | 0.512 | 4.0 | 0.392 |
| 100 | discovery | 45 | 3 | positive | 0.424 | 4.0 | 0.392 |
| 101 | guard | 46 | 3 | negative | 0.446 | nan | nan |
| 102 | guard | 12 | 1 | negative | 0.463 | nan | nan |
| 103 | guard | 14 | 1 | negative | 0.621 | nan | nan |
| 104 | guard | 18 | 1 | negative | 0.870 | nan | nan |
| 105 | guard | 42 | 3 | negative | 0.522 | nan | nan |
| 106 | guard | 46 | 3 | negative | 0.446 | nan | nan |

# Cases where repair helped (for balance)


## Case: realcartest_3200_3830 budget=6 seed=0

- event_recall_diff (core - nr): +0.286
- unique_bin_diff: +5
- repair_calls: 0

| idx | type | bin | chunk | label | prior |
|---|---|---|---|---|---|
| 0 | audit | 62 | 5 | negative | 0.729 |
| 1 | discovery | 12 | 1 | negative | 0.463 |
| 2 | discovery | 8 | 0 | negative | 0.671 |
| 3 | discovery | 9 | 0 | negative | 0.906 |
| 4 | discovery | 52 | 4 | positive | 0.708 |
| 5 | discovery | 58 | 4 | positive | 1.000 |
| 6 | guard | 51 | 4 | positive | 0.895 |
| 7 | guard | 50 | 4 | negative | 0.895 |
| 8 | guard | 53 | 4 | negative | 0.706 |
| 9 | guard | 57 | 4 | negative | 0.788 |
| 10 | guard | 59 | 4 | negative | 1.000 |

## Case: dataset3_1200_2400 budget=10 seed=0

- event_recall_diff (core - nr): +0.250
- unique_bin_diff: +4
- repair_calls: 0

| idx | type | bin | chunk | label | prior |
|---|---|---|---|---|---|
| 0 | audit | 119 | 9 | negative | 0.233 |
| 1 | discovery | 112 | 9 | negative | -0.672 |
| 2 | discovery | 18 | 1 | negative | 1.138 |
| 3 | discovery | 62 | 5 | negative | 0.233 |
| 4 | discovery | 6 | 0 | negative | -1.275 |
| 5 | discovery | 33 | 2 | negative | 1.138 |
| 6 | discovery | 55 | 4 | positive | 0.535 |
| 7 | discovery | 75 | 6 | positive | -0.069 |
| 8 | discovery | 41 | 3 | positive | -0.974 |
| 9 | discovery | 73 | 6 | negative | -1.879 |
| 10 | guard | 40 | 3 | negative | -0.370 |
| 11 | guard | 42 | 3 | negative | -0.974 |
| 12 | guard | 54 | 4 | positive | -0.069 |
| 13 | guard | 53 | 4 | positive | -0.974 |
| 14 | guard | 52 | 4 | positive | 0.836 |
| 15 | guard | 56 | 4 | positive | -0.069 |
| 16 | guard | 57 | 4 | positive | -0.974 |
| 17 | guard | 58 | 4 | positive | -1.275 |
| 18 | guard | 74 | 6 | negative | -1.879 |

## Case: realcartest_0_1570 budget=31 seed=0

- event_recall_diff (core - nr): +0.200
- unique_bin_diff: +6
- repair_calls: 1

| idx | type | bin | chunk | label | prior |
|---|---|---|---|---|---|
| 0 | audit | 114 | 9 | positive | 1.000 |
| 1 | audit | 107 | 8 | positive | 1.000 |
| 2 | audit | 98 | 8 | positive | 0.769 |
| 3 | audit | 144 | 12 | negative | 1.000 |
| 4 | audit | 99 | 8 | negative | 1.000 |
| 5 | audit | 67 | 5 | negative | 0.544 |
| 6 | audit | 39 | 3 | negative | 0.799 |
| 7 | audit | 21 | 1 | negative | 0.461 |
| 8 | repair | 97 | 8 | negative | 0.716 |
| 9 | discovery | 131 | 10 | negative | 0.307 |
| 10 | discovery | 110 | 9 | negative | 1.000 |
| 11 | discovery | 69 | 5 | negative | 1.000 |
| 12 | discovery | 45 | 3 | negative | 0.921 |
| 13 | discovery | 52 | 4 | negative | 0.957 |
| 14 | discovery | 127 | 10 | negative | 0.535 |
| 15 | discovery | 56 | 4 | positive | 0.739 |
| 16 | discovery | 145 | 12 | negative | 1.000 |
| 17 | discovery | 129 | 10 | negative | 0.486 |
| 18 | discovery | 19 | 1 | negative | 1.000 |
| 19 | discovery | 60 | 5 | negative | 0.656 |
| 20 | discovery | 58 | 4 | positive | 0.942 |
| 21 | discovery | 83 | 6 | negative | 1.000 |
| 22 | discovery | 156 | 13 | negative | 0.972 |
| 23 | discovery | 32 | 2 | negative | 0.572 |
| 24 | discovery | 55 | 4 | positive | 0.846 |
| 25 | discovery | 97 | 8 | negative | 0.716 |
| 26 | discovery | 50 | 4 | positive | 1.000 |
| 27 | discovery | 54 | 4 | negative | 0.916 |
| 28 | discovery | 59 | 4 | negative | 0.924 |
| 29 | discovery | 91 | 7 | negative | 0.583 |
| 30 | discovery | 155 | 12 | negative | 1.000 |
| 31 | guard | 53 | 4 | positive | 0.929 |
| 32 | guard | 52 | 4 | negative | 0.957 |
| 33 | guard | 57 | 4 | positive | 0.739 |
| 34 | guard | 58 | 4 | positive | 0.942 |
| 35 | guard | 59 | 4 | negative | 0.924 |
| 36 | guard | 57 | 4 | positive | 0.739 |
| 37 | guard | 56 | 4 | positive | 0.739 |
| 38 | guard | 55 | 4 | positive | 0.846 |
| 39 | guard | 61 | 5 | negative | 0.433 |
| 40 | guard | 96 | 8 | negative | 0.830 |
| 41 | guard | 100 | 8 | negative | 1.000 |
| 42 | guard | 49 | 4 | negative | 0.671 |
| 43 | guard | 51 | 4 | negative | 1.000 |
| 44 | guard | 106 | 8 | positive | 0.988 |
| 45 | guard | 105 | 8 | positive | 0.951 |
| 46 | guard | 104 | 8 | negative | 0.951 |
| 47 | guard | 108 | 9 | positive | 1.000 |
| 48 | guard | 109 | 9 | negative | 1.000 |
| 49 | guard | 113 | 9 | positive | 1.000 |
| 50 | guard | 112 | 9 | positive | 1.000 |
| 51 | guard | 111 | 9 | positive | 1.000 |
| 52 | guard | 115 | 9 | positive | 1.000 |
