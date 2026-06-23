#!/usr/bin/env python3
"""Verify proxy features and print summary stats."""
import csv
from collections import Counter

with open('/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1/tables/proxy_features_5s.csv') as f:
    rows = list(csv.DictReader(f))
print(f'Total rows: {len(rows)}')
print(f'Columns: {list(rows[0].keys())}')
vehicles = [float(r['vehicle_count_mean']) for r in rows]
objects = [float(r['object_count_mean']) for r in rows]
motions = [float(r['motion_energy_mean']) for r in rows]
print(f'vehicle_count >0: {sum(1 for v in vehicles if v > 0)}/{len(rows)}')
print(f'Mean vehicles/clip: {sum(vehicles)/len(vehicles):.2f}')
print(f'Max vehicles: {max(vehicles):.0f}')
print(f'Mean objects/clip: {sum(objects)/len(objects):.2f}')
print(f'Max objects: {max(objects):.0f}')
print(f'Motion mean: {sum(motions)/len(motions):.2f}')
print(f'Motion max: {max(motions):.2f}')
status_counts = Counter(r.get('yolo_status','?') for r in rows)
print(f'YOLO status counts:')
for s, c in status_counts.most_common():
    print(f'  {s}: {c}')
