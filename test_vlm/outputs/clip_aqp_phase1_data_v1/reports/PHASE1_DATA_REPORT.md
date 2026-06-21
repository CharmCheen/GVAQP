# Phase 1 Data Report: Event-Boundary Benchmark Ingestion

## Work Completed

- Created Phase 1 output directory: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_data_v1`
- Created external dataset directories under `/qiuyeqing/llama_prl/G-ARC/datasets/casq_external`
- Wrote mapping READMEs for DoTA, DADA-2000, Nexar, and Micro-CASQ-v0
- Defined unified CASQ event and unit schemas
- Wrote conservative converter scaffolds for all candidate datasets
- Wrote Micro-CASQ-v0 annotation template
- Wrote data plan and event-count target plan

## Local Dataset Status

| dataset | local directory | local raw annotations | CASQ conversion now |
| --- | --- | --- | --- |
| DoTA | exists | missing | skipped; no boundaries invented |
| DADA-2000 | exists | missing | skipped; no boundaries invented |
| Nexar | exists | missing | skipped; no boundaries invented |
| Micro-CASQ-v0 | exists | empty template exists | ready for manual annotation |

## Dataset Decision Basis

Nexar is the recommended first controlled subset because public documentation verifies positive-case temporal labels with `time_of_event` and `time_of_alert`, and the dataset includes normal-driving negatives. It is best matched to `collision_or_near_collision_precursor`.

DoTA is the recommended large follow-up because public documentation verifies temporal anomaly boundaries via `anomaly_start` and `anomaly_end`, and the dataset is larger. It needs fps verification and CASQ event-type adjudication before clean second-based ingestion.

DADA-2000 remains a backup candidate. Public sources report accident intervals, but the locally inspected public split files do not expose the actual event-boundary fields. Its first use should be an access/schema audit, not immediate benchmark construction.

Micro-CASQ-v0 is a clean manual fallback and smoke-test route, but it is not realistic for 200 / 500 events without significant manual annotation.

## Required Next Step

Ask for explicit approval to access/download a small Nexar subset:

- metadata only first if possible;
- 25 positive collision/near-collision videos;
- 25 normal-driving videos;
- license/terms snapshot;
- no full-dataset download.

If Nexar access is blocked, switch to a DoTA metadata-and-25-clip subset. If both are blocked, use Micro-CASQ-v0 manual annotation for a small clean smoke benchmark.

## Failed Or Deferred Hypotheses

- Existing Phase 0 pseudo-events are not sufficient as clean event-boundary data.
- Local dataset metadata is absent, so converters cannot yet produce CASQ events.
- DADA-2000 cannot be treated as locally boundary-verified from public split JSON files alone.
- Object-enters-ego-path is not cleanly available from any candidate without manual adjudication.

## Source Notes

- DoTA official repository documents metadata fields including `anomaly_start` and `anomaly_end`: https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly
- DADA-2000 / LOTVS-DADA official repository documents access paths and split files: https://github.com/JWFangit/LOTVS-DADA
- Nexar Hugging Face dataset card documents `time_of_event` and `time_of_alert`: https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction
- Nexar CVPRW 2025 paper documents event and alert temporal labels: https://openaccess.thecvf.com/content/CVPR2025W/WAD/papers/Moura_Nexar_Dashcam_Collision_Prediction_Dataset_and_Challenge_CVPRW_2025_paper.pdf

DATA_DECISION: READY_TO_DOWNLOAD_SMALL_SUBSET
