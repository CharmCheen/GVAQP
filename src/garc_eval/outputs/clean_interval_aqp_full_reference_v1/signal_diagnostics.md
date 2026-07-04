# Signal Diagnostics

Units evaluated against pseudo-oracle full reference: 600.

Positive units: 80 (0.133).

Best AUC signals:

| signal | auc | ap | base_positive_rate |
| --- | --- | --- | --- |
| primary_signal_score | 0.732897 | 0.341544 | 0.133333 |
| cheap_fused_score | 0.727187 | 0.266552 | 0.133333 |
| yolo_vehicle_count | 0.69595 | 0.258113 | 0.133333 |
| signal_disagreement | 0.651082 | 0.201975 | 0.133333 |
| object_density_change | 0.650601 | 0.246345 | 0.133333 |
| track_acceleration | 0.648101 | 0.177751 | 0.133333 |
| person_count | 0.638726 | 0.345179 | 0.133333 |
| relative_motion_score | 0.61012 | 0.156229 | 0.133333 |

Blind-spot rows generated: 121.

Interpretation limit: this stage intentionally uses full reference for diagnostics only. These metrics
must not be fed back into proposal generation or optimization in the main method.
