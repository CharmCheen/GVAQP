# STRIVE-D / DrivingDojo Asset Audit v1

Audit date: 2026-06-18 UTC

Decision: `PARTIAL_GO_CONTACT_AUTHORS`

## Scope

This is a read-only external asset audit for deciding whether STRIVE-D / DrivingDojo already expose enough public resources to support a query-conditioned symbolic-vs-proxy boundary study in this repository.

No human audit, VLM inference, training, large-file download, or experiment run was performed. Only public papers, project pages, repository READMEs/docs, and lightweight dataset metadata were inspected.

## Sources Checked

| Source | URL | What was checked |
|---|---|---|
| STRIVE-D paper | https://arxiv.org/abs/2606.09109 | Title, abstract, method, experiment setup, appendix A.1-A.6, query/event annotation description, release claims |
| STRIVE-D HTML paper | https://arxiv.org/html/2606.09109v1 | Searchable details for DrivingDojo event annotation, rule library, perception pipeline, metrics, prompts |
| DrivingDojo paper | https://arxiv.org/abs/2410.10738 | Dataset purpose, scale, task framing, project page linkage |
| DrivingDojo project page | https://drivingdojo.github.io/ | Public links to paper, GitHub, data-mini, HuggingFace dataset |
| DrivingDojo GitHub | https://github.com/Robertwyq/Drivingdojo | README, dataset docs, license, implementation purpose |
| DrivingDojo dataset docs | https://github.com/Robertwyq/Drivingdojo/blob/main/docs/DATASET.md | Expected dataset structure, video count, subset metadata description |
| DrivingDojo HuggingFace | https://huggingface.co/datasets/Yuqi1997/DrivingDojo | Dataset gating, license tag, visible file listing and storage metadata |
| DrivingDojo-mini HuggingFace | https://huggingface.co/datasets/jiaweihe/DrivingDojo-mini | Lightweight subset existence and file listing |
| NeurIPS 2024 DrivingDojo page | https://proceedings.neurips.cc/paper_files/paper/2024/hash/178f4666a84ecdd61e3b85145ed56484-Abstract-Datasets_and_Benchmarks_Track.html | Publication status |

## STRIVE-D Public Resource Status

| Resource needed | Public status | Evidence / notes | Supports immediate reuse? |
|---|---:|---|---:|
| Source code | Not found | arXiv page exposes no concrete official code link; web/GitHub searches for STRIVE-D and the paper title found no obvious repository. | No |
| Calibrated rule library | Not found | Paper describes calibrated symbolic rules, L2R calibration, hard gates, soft scores, and event mining, but no downloadable library file or schema was found. | No |
| DrivingDojo event annotation files | Claimed, not found | Appendix A.6 says the authors annotate 583 DrivingDojo videos and release the annotations alongside the paper. No public file entry was found in searched sources. | No |
| Query list | Partially described, file not found | Paper describes 41 natural-language queries across Cut-In, Cut-Out, Lane Change, and Turn. No machine-readable query file was found. | No |
| Evaluation split | Not found | Paper defines a 583-video retrieval pool but no split file or video id manifest was found. | No |
| Retrieval protocol | Partially described | Metrics are top-k accuracy, MRR, and mAP; reranking pool size K'=20 is stated. A runnable protocol/config is not public. | Partial |
| Perception output schema | Partially described | Paper describes per-frame structured representations with entities, attributes, distance, lane and motion signals. No concrete output schema file was found. | No |
| License for STRIVE-D assets | Not found | arXiv has its own non-exclusive license notice, but no license was found for annotation files, rules, code, or benchmark assets. | No |

### STRIVE-D Benchmark Facts Found In Paper

The paper title is "Driving Video Retrieval for Complex Queries with Structured Grounding" by Manyi Yao, Sparsh Garg, Christian Shelton, Amit Roy-Chowdhury, and Abhishek Aich.

The paper states that STRIVE-D evaluates on three dashcam corpora. For DrivingDojo, it reports:

- 583 annotated DrivingDojo videos.
- 41 distinct motion-event queries.
- 236 unique positive videos for at least one query.
- Each query has 1 to 138 relevant videos.
- Event families:
  - Cut-In, surrounding vehicle, 18 queries, 2-138 videos.
  - Cut-Out, surrounding vehicle, 17 queries, 1-80 videos.
  - Lane Change, ego vehicle, 3 queries, 47-98 videos.
  - Turn, ego vehicle, 3 queries, 38-92 videos.
- Cut-In/Cut-Out are stratified by object class and direction; Lane Change/Turn use ego vehicle directional variants.

These facts are enough to motivate an external benchmark, but not enough to reproduce it without the released annotation/query files.

## DrivingDojo Public Resource Status

| Resource needed | Public status | Evidence / notes | Supports STRIVE-D-style benchmark? |
|---|---:|---|---:|
| Video download method | Available but gated / large | HuggingFace dataset `Yuqi1997/DrivingDojo` is public but gated; visible metadata lists videos tarballs plus `action_info.tar.gz`, `camera_info.tar.gz`, and `meta.json`. | Partial |
| Dataset scale | Available | GitHub docs state DrivingDojo has 18k videos; HF metadata reports `size_categories:n>1T` and visible used storage about 312 GB for the inspected repo shard. Docs mention 45 tar.gz files across multiple repositories. | Partial |
| Subset / metadata | Available in principle | GitHub docs mention `data/dojo_subset.json` for action/interplay/open subsets and dataset structure with videos, action_info, camera info, and meta.json. | Partial |
| Action annotations | Available in principle | HF lists `action_info.tar.gz`; GitHub docs describe action-conditioned generation. This is not the same as STRIVE-D event retrieval labels. | Partial |
| Event annotations | Not found | No public DrivingDojo source inspected exposes STRIVE-D query-conditioned event annotations. | No |
| Video identifiers matching STRIVE-D 583 videos | Not found | STRIVE-D identifies a 583-video subset, but the exact video id list was not found. | No |
| License | Mixed | HF dataset metadata tags DrivingDojo as Apache-2.0. The GitHub code repository license file is GPL-3.0. STRIVE-D annotation/license is not found. | Needs review |
| Storage feasibility | Heavy | Full dataset is too large for an audit-stage pull and should not be downloaded without a controlled subset plan. | No immediate full pull |

DrivingDojo is a useful upstream video/metadata source, but the public resources inspected are primarily for interactive driving world models and action-conditioned video generation, not for STRIVE-D query-conditioned retrieval evaluation.

## Task Support Assessment

| Desired study component | Supported from public assets now? | Assessment |
|---|---:|---|
| Video-level query retrieval | No | STRIVE-D paper defines the task and metrics, but query-to-positive mappings and the 583-video manifest are missing. |
| Query-conditioned candidate coverage | No | Requires query list plus positive videos per query. The event taxonomy alone is insufficient. |
| Temporal interval evaluation | No | STRIVE-D paper describes video-level retrieval positives; no temporal interval annotation file was found. DrivingDojo action/camera metadata does not provide query-conditioned event intervals. |
| Cross-video generalization | Partial | DrivingDojo has many videos and metadata, but STRIVE-D benchmark split/protocol is missing. A custom split would no longer be the released STRIVE-D benchmark. |
| Calibrated symbolic rule comparison | No | The paper describes the rule machinery, but the calibrated rule library, thresholds, perception schema, and runnable implementation were not found. |

## Directly Reusable Public Content

- STRIVE-D paper descriptions of:
  - task framing for query-to-video retrieval;
  - metrics: Acc@k, MRR, mAP;
  - reranking pool size K'=20;
  - event families and counts for the DrivingDojo annotation set;
  - high-level symbolic rule components: entity selectors, hard gates, soft scores;
  - prompt text and methodological descriptions in appendices.
- DrivingDojo public resources:
  - project page and paper;
  - GitHub implementation for world-model training/AIF metric;
  - dataset structure documentation;
  - gated HuggingFace dataset metadata and file listing;
  - public mini dataset entry, without downloading it in this audit.

## Claimed But Not Found Public Entry

- STRIVE-D DrivingDojo annotation release:
  - 583-video subset identifiers;
  - 41 query list;
  - query-to-positive video mapping;
  - annotation schema;
  - license;
  - benchmark split/protocol files.
- STRIVE-D source code.
- Calibrated symbolic rule library.
- Perception output schema and generated structured features used by STRIVE-D.
- Exact retrieval configs and reranker settings as runnable artifacts.

## Must Contact Authors For

Request the following lightweight assets before downloading large video data:

1. `videos_583.tsv`: DrivingDojo video ids used in STRIVE-D.
2. `queries_41.tsv/json`: query id, natural-language query, event type, object class, direction, any aliases.
3. `relevance.tsv`: query id to positive video id mapping, including whether labels are video-level or interval-level.
4. `splits.json`: retrieval pool, development/test split if used, and any random seeds.
5. `rules/`: calibrated symbolic rule definitions, thresholds, hard gates, soft scores, entity selector definitions.
6. `perception_schema.md/json`: per-frame structured representation schema and expected detector/tracker/lane/distance fields.
7. `LICENSE`: terms for annotations, rules, code, and any derivative benchmark use.
8. Optional precomputed features/scores for the 583 videos, if they are intended to avoid full perception recomputation.

## Differences From Current G-ARC Pipeline

| Current G-ARC / VLM-budget pipeline | STRIVE-D / DrivingDojo assets |
|---|---|
| Clip/frame rows with source video, start/end, cheap scores, pseudo-oracle labels | Video-level retrieval pool with natural-language queries and event labels |
| Evaluation over VLM-defined pseudo-events or pseudo-label positives | Paper claims human event annotations, but files are not public in inspected sources |
| Proxy methods are score columns over clips | STRIVE-D uses dense retrieval, sparse retrieval, symbolic rules, reranking, and fusion |
| Leakage checks require source-video group split | STRIVE-D needs video id split/protocol and query-level relevance mapping |
| Event recall and candidate coverage can be computed from local tables | Query-conditioned coverage requires query-to-video positives and possibly temporal labels |
| Conservative labels are evaluation-only | STRIVE-D labels would be benchmark evaluation labels; if obtained, they must not be used to train/tune proxy methods for main conclusions |

## Minimal Viable External Benchmark Plan

Do not download full DrivingDojo yet.

Phase 1 should be author-contact / metadata-only:

- Obtain the 583-video manifest, 41 query list, relevance file, split/protocol, annotation license, and rule/perception schema.
- Validate that the 583 video ids correspond to accessible DrivingDojo video files or a controlled subset.
- Inspect whether labels are video-level only or contain temporal intervals.

Phase 2 should be a controlled subset only if Phase 1 succeeds:

- Download only a small subset of videos needed for schema and adapter smoke testing.
- Build a G-ARC adapter that maps `query_id`, `video_id`, `source_video`, optional `event_start/end`, and cheap/rule/proxy score columns.
- Compare symbolic/rule-like proposals against cheap proxy/rank fusion only after confirming no query labels are used in training/tuning.

If STRIVE-D annotations remain unavailable, a custom DrivingDojo benchmark can be built only as an engineering development set, not as an external STRIVE-D reproduction.

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| STRIVE-D annotation release not actually public yet | Cannot run official benchmark | Contact authors before implementation |
| Video id mismatch between STRIVE-D subset and public DrivingDojo files | Cannot reproduce retrieval pool | Request exact manifest and verify against HF metadata before download |
| License mismatch | Cannot redistribute derived benchmark | Request explicit annotation/rule license |
| Full dataset too large | Storage/time blow-up | Use metadata and a controlled subset first |
| No temporal interval labels | Boundary study may be video-level only | Separate video-level query retrieval from temporal interval evaluation |
| Rule library absent | Cannot compare calibrated symbolic rules | Treat self-authored rules as non-reproduction baseline only |

## Final Decision

`PARTIAL_GO_CONTACT_AUTHORS`

The public papers and DrivingDojo metadata are sufficient to justify contacting the STRIVE-D authors and planning a lightweight adapter, but they are not sufficient to start an official query-conditioned symbolic-vs-proxy boundary benchmark. The missing blockers are the STRIVE-D annotation files, exact 583-video manifest, query list, split/protocol, calibrated rule library, perception schema, and asset license.
