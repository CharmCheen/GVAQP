# Paper Reproduction Matrix

This matrix covers experiments from the SUPG and ABae papers, tracking which are
reproducible with the current G-ARC repository.

**Important**: BDD100K experiments in this repo are G-ARC extensions, NOT from the
original SUPG/ABae papers. They are listed separately.

---

## SUPG Paper Experiments

| # | Paper Ref | Experiment | Dataset | Oracle/Proxy Needed | Repo Support | Data Available | Runnable Now | Blocker | Script | Output Report |
|---|-----------|------------|---------|---------------------|--------------|----------------|--------------|---------|--------|---------------|
| S1 | Fig 2/3 | Synthetic Beta(0.01,1) failure/quality | Synthetic | None | Yes (make_beta, run_supg_synthetic) | Generated | YES | - | `run_supg_synthetic --alpha 0.01 --beta 1.0` | `supg_paper_synthetic_reproduction/report.md` |
| S2 | Fig 2/3 | Synthetic Beta(0.01,2) failure/quality | Synthetic | None | Yes | Generated | YES | - | `run_supg_synthetic --alpha 0.01 --beta 2.0` | `supg_paper_synthetic_reproduction/report.md` |
| S3 | Fig 4 | ImageNet hummingbird selection | ImageNet | YOLO/human oracle | No ImageNet loader | No | NO | Need ImageNet subset + oracle labels | - | - |
| S4 | Fig 5 | Night-street car selection | BDD100K/night-street | YOLO oracle | Yes (run_supg_real_frames) | Cached (bdd100k_smoke) | YES (G-ARC extension) | - | `run_supg_real_frames --source-csv garc_eval/outputs/bdd100k_smoke/supg_source.csv` | `bdd100k_formal_100trials/report.md` |
| S5 | Table 2 | OntoNotes entity selection | OntoNotes | NER oracle | No OntoNotes loader | No | NO | Need OntoNotes + NER oracle | - | - |
| S6 | Table 2 | TACRED relation selection | TACRED | RE oracle | No TACRED loader | No | NO | Need TACRED + RE oracle | - | - |
| S7 | Fig 6 | Model drift robustness | Synthetic | None | No drift script | Can generate | NO | Need drift simulation script | - | - |
| S8 | Fig 7 | Proxy noise sensitivity | Synthetic | None | No noise script | Can generate | NO | Need noise injection script | - | - |
| S9 | Fig 8 | Class imbalance sensitivity | Synthetic | None | No imbalance script | Can generate | NO | Need imbalance sweep script | - | - |
| S10 | Fig 9 | Importance exponent (gamma) sensitivity | Synthetic | None | Yes (run_supg_synthetic --gamma) | Generated | YES | - | `run_supg_synthetic --gamma 0.5/0.7/0.9/0.95` | `supg_paper_synthetic_reproduction/report.md` |
| S11 | Sec 5.3 | CI method comparison (percentile vs bootstrap) | Synthetic | None | Partial (percentile only) | Generated | PARTIAL | Need BCa/bootstrap variants | - | - |
| S12 | Sec 5.4 | Cost analysis (oracle calls saved) | Synthetic | None | Yes (sampled_n in results) | Generated | YES | - | Same as S1/S2 | `supg_paper_synthetic_reproduction/report.md` |

## ABae Paper Experiments

| # | Paper Ref | Experiment | Dataset | Oracle/Proxy Needed | Repo Support | Data Available | Runnable Now | Blocker | Script | Output Report |
|---|-----------|------------|---------|---------------------|--------------|----------------|--------------|---------|--------|---------------|
| A1 | Fig 3 | Single-predicate RMSE vs budget | Synthetic | None | Yes (run_abae_synthetic) | Generated | YES | - | `run_abae_synthetic --budgets 500 1000 2000 5000 10000` | `abae_paper_synthetic_reproduction/report.md` |
| A2 | Fig 3 | Low-budget RMSE | Synthetic | None | Yes | Generated | YES | - | Same as A1 | `abae_paper_synthetic_reproduction/report.md` |
| A3 | Fig 4 | Q-error / relative error | Synthetic | None | Yes (aggregation_metrics) | Generated | YES | - | Same as A1 | `abae_paper_synthetic_reproduction/report.md` |
| A4 | Fig 5 | CI width | Synthetic | None | Yes | Generated | YES | - | Same as A1 | `abae_paper_synthetic_reproduction/report.md` |
| A5 | Fig 5 | CI coverage | Synthetic | None | Yes | Generated | YES | - | Same as A1 | `abae_paper_synthetic_reproduction/report.md` |
| A6 | Table 3 | Night-street car aggregation | BDD100K | YOLO oracle | Yes (run_abae_real_frames) | Cached (bdd100k_smoke) | YES (G-ARC extension) | - | `run_abae_real_frames` | `abae_bdd100k_smoke/report.md` |
| A7 | Table 3 | Taipei intersection aggregation | Taipei | Oracle labels | No loader | No | NO | Need dataset + oracle | - | - |
| A8 | Table 3 | CelebA attribute aggregation | CelebA | Attribute oracle | No loader | No | NO | Need CelebA subset | - | - |
| A9 | Table 3 | Amazon movie posters aggregation | Amazon | Oracle labels | No loader | No | NO | Need dataset | - | - |
| A10 | Table 3 | trec05p spam aggregation | trec05p | Spam oracle | No loader | No | NO | Need dataset | - | - |
| A11 | Table 3 | Amazon office aggregation | Amazon | Oracle labels | No loader | No | NO | Need dataset | - | - |
| A12 | Sec 4.3 | MultiPred aggregation | Synthetic | None | No MultiPred impl | Can generate | NO | Need MultiPred extension | - | - |
| A13 | Sec 4.4 | GroupBy single oracle | Synthetic | None | No GroupBy impl | Can generate | NO | Need GroupBy extension | - | - |
| A14 | Sec 4.4 | GroupBy multiple oracle | Synthetic | None | No GroupBy impl | Can generate | NO | Need GroupBy extension | - | - |
| A15 | Sec 5.1 | Lesion: no sample reuse vs uniform | Synthetic | None | Partial | Generated | YES | - | `run_abae_synthetic` (uniform mode) | `abae_paper_synthetic_reproduction/report.md` |
| A16 | Sec 5.2 | Sensitivity: strata K | Synthetic | None | Yes (--num-strata) | Generated | YES | - | `run_abae_synthetic --num-strata 5/10/20` | `abae_paper_synthetic_reproduction/report.md` |
| A17 | Sec 5.2 | Sensitivity: stage1 fraction C | Synthetic | None | Yes (--stage1-per-stratum) | Generated | YES | - | `run_abae_synthetic --stage1-per-stratum 10/20/50` | `abae_paper_synthetic_reproduction/report.md` |
| A18 | Sec 5.3 | Proxy combination | Synthetic | None | No multi-proxy impl | Can generate | NO | Need multi-proxy extension | - | - |

## G-ARC Extension Experiments (NOT from original papers)

| # | Extension | Experiment | Dataset | Runnable Now | Output Report |
|---|-----------|------------|---------|--------------|---------------|
| E1 | BDD100K SUPG | 100-trial formal selection | BDD100K cached | YES (cached) | `bdd100k_formal_100trials/report.md` |
| E2 | BDD100K ABae | 30-trial aggregation smoke | BDD100K cached | YES (cached) | `abae_bdd100k_smoke/report.md` |
| E3 | BDD100K ABae COUNT | 100-trial COUNT coverage diagnostic | BDD100K cached | YES (cached) | `abae_bdd100k_count_coverage/report.md` |

---

## Summary

- **SUPG runnable now**: S1, S2, S4 (extension), S10, S12
- **SUPG blocked**: S3, S5, S6, S7, S8, S9, S11 (partial)
- **ABae runnable now**: A1-A5, A6 (extension), A15, A16, A17
- **ABae blocked**: A7-A14, A18
- **G-ARC extension**: E1-E3 (cached BDD100K)

Generated: 2026-05-20
