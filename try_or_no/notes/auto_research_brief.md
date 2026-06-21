# Auto Research Brief

## Goal

Explore whether we can bypass fixed task-specific proxy models for moving-camera relevant clip queries.

Important clarification:
- We do NOT mean bypassing all cheap information.
- We mean bypassing ARC/SUPG/ABae-style fixed proxy scores or proxy models.
- The alternative is query-agnostic temporal preprocessing + limited oracle calibration.

## Available Code

Main working directory:
- /qiuyeqing/llama_prl/G-ARC/try_or_no

Reference systems:
- ARC source: /qiuyeqing/llama_prl/G-ARC/try_or_no/arc_source
- SUPG source: /qiuyeqing/llama_prl/G-ARC/refe_repos/supg
- ABae source: /qiuyeqing/llama_prl/G-ARC/refe_repos/abae

Existing experimental outputs:
- /qiuyeqing/llama_prl/G-ARC/try_or_no/outputs
- /qiuyeqing/llama_prl/G-ARC/try_or_no/scripts

## Current Empirical Evidence

We already ran ARC-style moving-camera stress tests on realcar_5k.

Main findings:
1. ARC / hard proxy can fail on moving-camera high-threshold clip queries.
2. Frame-level proxy and pseudo-oracle can be correlated, but proxy positives may be sparse and fragmented.
3. Adaptive relaxed proxy candidate generation works:
   - It decouples oracle query threshold Kq and proxy candidate threshold Kp.
   - It triggers relaxation only when hard proxy is sparse or fragmented.
   - It uses gap stitching to repair fragmented proxy positives.
4. On realcar_5k:
   - For Kq=13, hard proxy R@0.5 = 0.
   - Adaptive selected Kp=10 and reached R@0.5 = 1.0, coverage = 1.0, with controlled candidate frame fraction.
5. Strict IoU@0.9 is not solved by current budgeted boundary refinement.
6. Expanded candidate upper bound shows high-IoU is theoretically recoverable, but current refinement is too weak.

## Research Question

Can a video query system answer moving-camera relevant clip queries without relying on fixed task-specific proxy pruning?

More concretely:
Can query-agnostic temporal synopsis + limited oracle calibration generate relevant clip candidates as well as or better than adaptive relaxed proxy generation?

## Required Auto Research Discipline

Do not write a paper.
Do not decide the final thesis.
Do not modify ARC/SUPG/ABae core code.
Do not train models.
Do not download external datasets.
Do not run long experiments without confirmation.

Use an iterative loop:
1. Read code and previous reports.
2. State one hypothesis.
3. Propose one minimal experiment.
4. Run only that experiment after confirmation.
5. Produce evidence, counter-evidence, uncertainty, and next step.
6. Stop for human checkpoint.

## First Desired Output

Only create:
- outputs/auto_research/state_index.md
- outputs/auto_research/hypotheses_v1.md
- outputs/auto_research/proxy_bypass_experiment_plan.md

Do not run experiments in the first pass.
