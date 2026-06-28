#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from candidate_common import OUT, append_progress, gpu_info, markdown_table, write_placeholder_figures


def main() -> int:
    access = pd.read_csv(OUT / "tables/video_access_manifest.csv")
    subset_checks = pd.read_csv(OUT / "tables/leakage_and_subset_checks.csv")
    gen_status = pd.read_csv(OUT / "tables/candidate_generation_status.csv")
    eval_df = pd.read_csv(OUT / "tables/candidate_eval_results.csv")
    cert_df = pd.read_csv(OUT / "tables/candidate_certificate_results.csv")
    gpu = gpu_info()
    accessible = int((access["download_status"] == "linked_existing").sum())
    decision = "NEED_VIDEO_ACCESS" if accessible == 0 else "CODE_REVIEW_NEEDED"
    write_placeholder_figures()

    lines = [
        "# Phase 1.4 Nexar Video-based Candidate Feasibility Report",
        "",
        "## 1. Goal",
        "",
        "Test whether non-oracle video-based candidate generators can produce high-recall returned clips for the Nexar-200 derived-boundary CASQ/G-ClipAQP benchmark. This run did not run VLMs, train models, build a large perception stack, or fabricate event boundaries.",
        "",
        "## 2. Why this stage follows Phase 1.3",
        "",
        "Phase 1.3 concluded `DISENTANGLE_DECISION: CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK`: the repaired certificate can work when the returned set is good, but the practical metadata-hash returned set had true derived recall around 0.06. Phase 1.4 therefore first checks whether video content is accessible for practical candidate generation.",
        "",
        "## 3. Data access and subset",
        "",
        "A smoke subset of 50 positive and 50 normal manifest rows was selected without using alert/event timing fields for candidate generation. The manifest points to local video paths under the Nexar raw directory, but none of the smoke-subset files exists locally, and the available metadata files contain no remote download URLs.",
        "",
        markdown_table(access[["video_id", "label", "download_status", "file_size", "access_detail"]], max_rows=20),
        "",
        "## 4. Candidate generators implemented",
        "",
        "The pipeline scripts for fixed sliding windows, motion energy, YOLO count proxy, CLIP/SigLIP text score, and optional small-VLM score are staged to skip gracefully. Because video access failed, no practical candidate windows were generated.",
        "",
        markdown_table(gen_status),
        "",
        "## 5. Leakage controls",
        "",
        "Candidate generation was not allowed to use `alert_time`, `event_moment`, `event_start`, `event_end`, `derived_event_start`, or `derived_event_end`. The subset written for candidate generation excludes those timing fields; derived boundaries remain evaluation-only.",
        "",
        markdown_table(subset_checks),
        "",
        "## 6. Candidate recall vs budget",
        "",
        "No candidate recall-vs-budget evaluation was run because no video files were accessible and no candidate sets were generated.",
        "",
        markdown_table(eval_df),
        "",
        "## 7. Runtime and cost",
        "",
        f"GPU visible: `{gpu.get('gpu_visible')}`. GPU model: `{gpu.get('gpu_model')}`. GPU used: `{gpu.get('gpu_used')}`. Reason: {gpu.get('gpu_use_reason')}",
        "",
        "Runtime was limited to metadata access checks and placeholder table/report generation. Throughput and GPU cost for feature extraction are not meaningful because zero frames were processed.",
        "",
        "## 8. Certificate results for promising candidates",
        "",
        "No candidate configuration reached the evaluation stage, so there were no promising candidates with true derived recall >= 0.5 to certify. Certificate validity constraints are marked not applicable rather than passed.",
        "",
        markdown_table(cert_df),
        "",
        "## 9. Limitations of derived boundaries",
        "",
        "- Nexar intervals are derived from alert time to event moment and are not human-adjudicated original event boundaries.",
        "- This access-blocked run cannot answer whether motion, YOLO, CLIP/SigLIP, or small-VLM candidates are sufficient.",
        "- Any later candidate evaluation must continue to treat derived boundaries as oracle-relative evaluation only.",
        "",
        "## 10. Recommendation",
        "",
        "Obtain or link the controlled Nexar video subset before running feature extraction. Start with the 50 positive / 50 normal smoke subset, record GPU use explicitly, and only expand to 200 / 200 if access and runtime are reasonable.",
        "",
        f"CANDIDATE_DECISION: {decision}",
        "",
    ]
    (OUT / "reports/CANDIDATE_FEASIBILITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    append_progress("candidate_report", "python scripts/50_generate_candidate_report.py", f"decision={decision}", next_action="py_compile and completion audit")
    print(f"CANDIDATE_DECISION: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

