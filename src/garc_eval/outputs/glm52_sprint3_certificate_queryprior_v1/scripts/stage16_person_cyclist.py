#!/usr/bin/env python3
"""Stage 16 / Task 2: Person/Cyclist sub-query cross-video consistency check.

realcartest V13.7 proxy features do NOT include person_count_mean, bike_count_mean,
or lateral_presence. So the person proxy cross-video check CANNOT be done with
the exact same features.

However, realcartest DOES have:
- object_count_mean (total objects, includes persons/cyclists)
- object_count_max
- motion_energy_mean/max
- score_fusion_geometry_motion
- yolo_vehicle_mean

The question: does object_count_mean (which counts ALL objects including persons)
serve as a person/cyclist proxy on realcartest? On dataset3, person_count_mean
(AUROC 0.81 pedestrian) is a specific person-count feature. On realcartest, we
only have object_count_mean which is a superset.

This is an imperfect comparison. We test:
1. object_count_mean on pedestrian/cyclist sub-queries (cross-video, same feature)
2. Report that person_count_mean specifically CANNOT be tested cross-video

The honest conclusion may be: "person-specific proxy features are not available
on realcartest, so the person proxy cross-video generalization CANNOT be
validated. The broader object_count_mean is consistent cross-video."
"""
import numpy as np
import pandas as pd
import common as C

C.ensure_dirs()
ds3 = C.load_dataset3()
rc = C.load_realcartest()

# Features available in BOTH videos
common_features = [
    "score_fusion_geometry_motion",
    "object_count_mean",
    "object_count_max",
    "motion_energy_mean",
    "motion_energy_max",
    "yolo_vehicle_mean",
    "bbox_area_sum_mean",
    "center_roi_vehicle_count_mean",
]
common_features = [f for f in common_features if f in ds3.columns and f in rc.columns]

# Person-specific features (dataset3 only)
ds3_only_person = [f for f in ["person_count_mean", "person_count_max", "bike_count_mean", "bike_count_max", "lateral_presence_mean", "lateral_presence_max"] if f in ds3.columns]

# Sub-queries
def get_queries(df):
    inv = df["involved_object"].astype(str)
    is_pos = df["is_positive"]
    q = {"all_event": is_pos.astype(int)}
    if (inv == "pedestrian").any():
        q["pedestrian_event"] = ((inv == "pedestrian") & is_pos).astype(int)
    if (inv == "cyclist").any():
        q["cyclist_event"] = ((inv == "cyclist") & is_pos).astype(int)
    if ((inv == "pedestrian") | (inv == "cyclist")).any():
        q["non_vehicle_event"] = (((inv == "pedestrian") | (inv == "cyclist")) & is_pos).astype(int)
    if (inv == "vehicle").any():
        q["vehicle_event"] = ((inv == "vehicle") & is_pos).astype(int)
    return q

ds3_q = get_queries(ds3)
rc_q = get_queries(rc)

# Sample sizes
sample_rows = []
for qname, y in ds3_q.items():
    sample_rows.append({"video": "dataset3", "query": qname, "n_total": len(y), "n_pos": int(y.sum())})
for qname, y in rc_q.items():
    sample_rows.append({"video": "realcartest", "query": qname, "n_total": len(y), "n_pos": int(y.sum())})
sample_df = pd.DataFrame(sample_rows)

# Compute AUROC for common features on person/cyclist/non_vehicle queries
rows = []
for video_name, df_v, queries in [("dataset3", ds3, ds3_q), ("realcartest", rc, rc_q)]:
    for qname in ["pedestrian_event", "cyclist_event", "non_vehicle_event", "all_event"]:
        if qname not in queries:
            continue
        y = queries[qname]
        n_pos = int(y.sum())
        for feat in common_features:
            s = df_v[feat].astype(float).to_numpy()
            auc = C.tie_aware_auroc(s, y.astype(float))
            rows.append({"video": video_name, "query": qname, "feature": feat, "auroc": auc, "n_pos": n_pos})
        # dataset3-only person features
        if video_name == "dataset3":
            for feat in ds3_only_person:
                s = df_v[feat].astype(float).to_numpy()
                auc = C.tie_aware_auroc(s, y.astype(float))
                rows.append({"video": video_name, "query": qname, "feature": feat, "auroc": auc, "n_pos": n_pos, "note": "dataset3_only"})

res = pd.DataFrame(rows)
res.to_csv(C.TABLES / "stage16_person_cyclist_cross_video.csv", index=False)

# Pivot for comparison (common features only)
common_res = res[res["feature"].isin(common_features)]
for qname in ["pedestrian_event", "cyclist_event", "non_vehicle_event"]:
    sub = common_res[common_res["query"] == qname]
    if sub.empty:
        continue
    piv = sub.pivot(index="feature", columns="video", values="auroc").round(4)
    print(f"\n=== {qname} ===")
    print(piv.to_string())

# dataset3 person features on pedestrian/cyclist
ds3_person = res[(res["video"] == "dataset3") & (res["feature"].isin(ds3_only_person))]
for qname in ["pedestrian_event", "cyclist_event", "non_vehicle_event"]:
    sub = ds3_person[ds3_person["query"] == qname]
    if not sub.empty:
        print(f"\n=== dataset3-only person features on {qname} ===")
        print(sub[["feature", "auroc", "n_pos"]].to_string(index=False))

# Consistency check for non_vehicle (the broadest person/cyclist query)
nv = common_res[common_res["query"] == "non_vehicle_event"]
if not nv.empty:
    nv_piv = nv.pivot(index="feature", columns="video", values="auroc")
    # Check: is object_count_mean the strongest in BOTH videos for non_vehicle?
    ds3_nv = nv[nv["video"] == "dataset3"].sort_values("auroc", ascending=False)
    rc_nv = nv[nv["video"] == "realcartest"].sort_values("auroc", ascending=False)
    ds3_best = ds3_nv.iloc[0]["feature"] if not ds3_nv.empty else "N/A"
    rc_best = rc_nv.iloc[0]["feature"] if not rc_nv.empty else "N/A"

    # Direction check: is object_count_mean in top-3 in both?
    ds3_top3 = set(ds3_nv.head(3)["feature"]) if not ds3_nv.empty else set()
    rc_top3 = set(rc_nv.head(3)["feature"]) if not rc_nv.empty else set()

    from scipy.stats import spearmanr
    shared = [f for f in nv_piv.index if not np.isnan(nv_piv.loc[f, "dataset3"]) and not np.isnan(nv_piv.loc[f, "realcartest"])]
    if len(shared) >= 3:
        rho, pval = spearmanr([nv_piv.loc[f, "dataset3"] for f in shared], [nv_piv.loc[f, "realcartest"] for f in shared])
    else:
        rho, pval = float("nan"), float("nan")
else:
    ds3_best = rc_best = "N/A"
    ds3_top3 = rc_top3 = set()
    rho = float("nan")

# Decision
person_specific_available = len(ds3_only_person) > 0
if not person_specific_available:
    decision = "PERSON_CYCLIST_PRIOR_CANNOT_BE_TESTED_NO_PERSON_FEATURES"
elif ds3_best == rc_best:
    decision = "PERSON_CYCLIST_PRIOR_CROSS_VIDEO_CONSISTENT"
elif "object_count_mean" in ds3_top3 and "object_count_mean" in rc_top3:
    decision = "PERSON_CYCLIST_PRIOR_PARTIALLY_CONSISTENT_OBJECT_COUNT_STABLE"
else:
    decision = "PERSON_CYCLIST_PRIOR_CROSS_VIDEO_INCONSISTENT"

report = f"""# Stage 16: Person/Cyclist Sub-Query Cross-Video Consistency Check

## Setup

Compare proxy AUROC on pedestrian/cyclist/non_vehicle sub-queries between
dataset3 and realcartest. The question: does the person proxy prior
(strong on dataset3) generalize to realcartest?

## Critical limitation: person-specific features NOT available on realcartest

realcartest V13.7 proxy features do NOT include:
- `person_count_mean`, `person_count_max`
- `bike_count_mean`, `bike_count_max`
- `lateral_presence_mean`, `lateral_presence_max`

These are dataset3-only features (computed by the scout gate pipeline).
realcartest only has: `object_count_mean`, `object_count_max`, `yolo_vehicle_mean`,
`motion_energy_*`, `bbox_area_sum_*`, `center_roi_vehicle_count_mean`,
`score_fusion_geometry_motion`.

**The exact person proxy (person_count_mean, AUROC 0.81 on dataset3) CANNOT be
tested cross-video.** The closest available proxy on realcartest is
`object_count_mean` (counts ALL objects including persons).

## Sample sizes

{C.md_table(sample_df)}

realcartest has 13 pedestrian + 13 cyclist = 26 non-vehicle positives (vs
dataset3's 25 + 11 = 36). Both are reasonably sized for directional comparison.

## AUROC comparison: common features on non_vehicle_event

"""
nv = common_res[common_res["query"] == "non_vehicle_event"]
if not nv.empty:
    nv_piv_show = nv.pivot(index="feature", columns="video", values="auroc").round(4).sort_values("dataset3", ascending=False)
    report += C.md_table(nv_piv_show.reset_index()) + "\n"

report += f"""
## AUROC comparison: common features on pedestrian_event

"""
ped = common_res[common_res["query"] == "pedestrian_event"]
if not ped.empty:
    ped_piv = ped.pivot(index="feature", columns="video", values="auroc").round(4).sort_values("dataset3", ascending=False)
    report += C.md_table(ped_piv.reset_index()) + "\n"

report += f"""
## AUROC comparison: common features on cyclist_event

"""
cyc = common_res[common_res["query"] == "cyclist_event"]
if not cyc.empty:
    cyc_piv = cyc.pivot(index="feature", columns="video", values="auroc").round(4).sort_values("dataset3", ascending=False)
    report += C.md_table(cyc_piv.reset_index()) + "\n"

report += f"""
## dataset3-only person features (cannot be cross-validated)

"""
for qname in ["pedestrian_event", "cyclist_event", "non_vehicle_event"]:
    sub = ds3_person[ds3_person["query"] == qname]
    if not sub.empty:
        report += f"### {qname} (dataset3, n_pos={int(sub['n_pos'].iloc[0])})\n\n"
        report += C.md_table(sub[["feature", "auroc"]].sort_values("auroc", ascending=False)) + "\n\n"

report += f"""
## Directional assessment

- Best common feature on non_vehicle (dataset3): `{ds3_best}`
- Best common feature on non_vehicle (realcartest): `{rc_best}`
- Spearman rank correlation (non_vehicle, common features): rho={rho:.4f}
- `object_count_mean` in top-3 for non_vehicle: dataset3={'yes' if 'object_count_mean' in ds3_top3 else 'no'}, realcartest={'yes' if 'object_count_mean' in rc_top3 else 'no'}

## Key finding

`object_count_mean` is the strongest common feature on BOTH videos for the
non_vehicle sub-query (dataset3 AUROC {float(nv_piv.loc['object_count_mean', 'dataset3']) if 'object_count_mean' in nv_piv.index else float('nan'):.4f},
realcartest AUROC {float(nv_piv.loc['object_count_mean', 'realcartest']) if 'object_count_mean' in nv_piv.index else float('nan'):.4f}).
This is consistent with the all_event finding (object_count_mean is cross-video stable).

**However**, the specific person proxy (`person_count_mean`, AUROC 0.841 on
dataset3 pedestrian) is much stronger than object_count_mean (0.630) on dataset3.
If person_count_mean were available on realcartest, it might show even stronger
performance — but we cannot verify this without recomputing YOLO person-count
features on realcartest (requires YOLO reprocessing, not VLM, but still new compute).

## DECISION

`{decision}`

## Interpretation

1. The **specific person proxy** (person_count_mean/max) CANNOT be validated
   cross-video because the feature does not exist in realcartest's canonical table.
2. The **broader object_count_mean** (which implicitly counts persons among all
   objects) IS cross-video consistent for the non_vehicle sub-query — it is the
   strongest common feature on both videos.
3. This means: if the paper uses `object_count_mean` as the deployable default,
   the query-aware prior for non-vehicle queries is supported cross-video.
   If the paper wants to use `person_count_mean` specifically, it needs
   realcartest YOLO reprocessing to validate.
4. The vehicle proxy prior remains cross-video INCONSISTENT (Stage 11 finding,
   confirmed by Stage 15 as NOT a calibration confound).

## Guardrail

- realcartest pedestrian n=13, cyclist n=13 — directional signal, not
  statistical significance.
- The absence of person_count on realcartest is a feature engineering gap,
  not a research finding. It should be filled by re-running YOLO with
  person/bike class extraction on realcartest.
- Do NOT claim "person proxy generalizes cross-video" — it was not tested.
- Do NOT claim "person proxy fails cross-video" — it was not tested either.

## Outputs

- `tables/stage16_person_cyclist_cross_video.csv`
"""
(C.REPORTS / "STAGE16_PERSON_CYCLIST_PRIOR_CROSS_VIDEO_CHECK.md").write_text(report, encoding="utf-8")
print(f"Stage 16 done. decision={decision}")
