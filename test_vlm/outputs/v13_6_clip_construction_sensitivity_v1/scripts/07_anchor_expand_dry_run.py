#!/usr/bin/env python3
"""Stage 7: Anchor-and-expand dry-run using sensitivity labels only."""
import csv, os, sys
from collections import Counter, defaultdict

ROOT = "/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1"
LABELS_CSV = f"{ROOT}/tables/clip_construction_vlm_labels.csv"

if not os.path.exists(LABELS_CSV):
    print("ERROR: VLM labels not yet available. Run Stage 4 first.")
    sys.exit(1)

rows = list(csv.DictReader(open(LABELS_CSV)))
ok = [r for r in rows if r.get("vlm_call_status","") == "ok"]

# Focus on center_10s policy as the proposed anchor
center_10s = [r for r in ok if r["construction_policy"] == "center_10s"]
print(f"center_10s clips: {len(center_10s)}")

positives = [r for r in center_10s if r["label"] == "positive"]
negatives = [r for r in center_10s if r["label"] == "negative"]
abstains = [r for r in center_10s if r["label"] == "abstain"]

print(f"  Positive: {len(positives)}")
print(f"  Negative: {len(negatives)}")
print(f"  Abstain: {len(abstains)}")

# Apply expansion rules
needs_left = 0
needs_right = 0
needs_both = 0
needs_refinement = 0
complete_without = 0
no_event = 0
needs_human = 0

for r in positives:
    bs = r.get("boundary_status", "")
    if bs == "ok":
        complete_without += 1
    elif bs == "truncated_start":
        needs_left += 1
    elif bs == "truncated_end":
        needs_right += 1
    elif bs == "truncated_both":
        needs_both += 1
    elif bs == "uncertain":
        needs_refinement += 1
    else:
        needs_refinement += 1  # unknown boundary

total_pos = len(positives)
fraction_complete = complete_without / total_pos if total_pos else 0
fraction_needing_expansion = (needs_left + needs_right + needs_both) / total_pos if total_pos else 0
fraction_needing_refinement = needs_refinement / total_pos if total_pos else 0

# Estimate extra calls
# Each "needs expansion" requires 1 extra call per direction (left or right)
extra_left_calls = needs_left + needs_both  # each truncated_start needs 1 left expansion
extra_right_calls = needs_right + needs_both  # each truncated_end needs 1 right expansion
extra_refinement_calls = needs_refinement  # uncertain -> needs 1 extra refinement call
total_extra = extra_left_calls + extra_right_calls + extra_refinement_calls

# Expected total calls: initial anchors + expansions
# For full video, estimate if using center_10s anchors uniformly
estimated_initial_anchors = 399  # from Stage 6: ceil(3987/10)
pos_rate = total_pos / len(center_10s) if center_10s else 0
estimated_pos_anchors = int(estimated_initial_anchors * pos_rate)
extra_per_pos = total_extra / total_pos if total_pos else 0
estimated_total_expansions = int(estimated_pos_anchors * extra_per_pos)
expected_total_calls = estimated_initial_anchors + estimated_total_expansions

print(f"\n=== ANCHOR-EXPAND DRY RUN (center_10s) ===")
print(f"Total positive clips: {total_pos}")
print(f"  Complete without expansion: {complete_without} ({fraction_complete:.2f})")
print(f"  Need left expansion: {needs_left} (truncated_start)")
print(f"  Need right expansion: {needs_right} (truncated_end)")
print(f"  Need both expansions: {needs_both} (truncated_both)")
print(f"  Need refinement: {needs_refinement} (uncertain)")
print(f"\nFraction needing any expansion: {fraction_needing_expansion:.2f}")
print(f"Estimated extra calls per positive: {extra_per_pos:.2f}")
print(f"\nFull-video projection (center_10s anchors):")
print(f"  Estimated initial anchors: {estimated_initial_anchors}")
print(f"  Estimated positive anchors: {estimated_pos_anchors}")
print(f"  Estimated expansions: {estimated_total_expansions}")
print(f"  Expected total calls: {expected_total_calls}")
print(f"  Ratio vs full 5s oracle: {expected_total_calls/798:.2f}")

# Write dry-run results
dry_run = [
    {"metric": "policy", "value": "center_10s_anchor_expand"},
    {"metric": "num_positive_clips_in_sample", "value": str(total_pos)},
    {"metric": "fraction_complete_without_expansion", "value": f"{fraction_complete:.4f}"},
    {"metric": "fraction_needing_left_expansion", "value": f"{needs_left/total_pos:.4f}" if total_pos else "0"},
    {"metric": "fraction_needing_right_expansion", "value": f"{needs_right/total_pos:.4f}" if total_pos else "0"},
    {"metric": "fraction_needing_both_expansion", "value": f"{needs_both/total_pos:.4f}" if total_pos else "0"},
    {"metric": "fraction_needing_refinement", "value": f"{fraction_needing_refinement:.4f}"},
    {"metric": "estimated_extra_calls_per_positive", "value": f"{extra_per_pos:.2f}"},
    {"metric": "estimated_initial_anchors_full_video", "value": str(estimated_initial_anchors)},
    {"metric": "estimated_expansions_full_video", "value": str(estimated_total_expansions)},
    {"metric": "expected_total_calls_full_video", "value": str(expected_total_calls)},
    {"metric": "ratio_vs_full_5s_oracle_798_calls", "value": f"{expected_total_calls/798:.3f}"},
    {"metric": "abstain_rate_in_center_10s", "value": f"{len(abstains)/len(center_10s):.4f}" if center_10s else "0"},
    {"metric": "estimated_human_or_defensive_samples", "value": str(int(estimated_initial_anchors * len(abstains)/len(center_10s))) if center_10s else "0"},
]

with open(f"{ROOT}/tables/anchor_expand_dry_run.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(dry_run)
print(f"\nWritten anchor_expand_dry_run.csv")
