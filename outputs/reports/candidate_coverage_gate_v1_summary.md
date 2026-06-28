# Candidate Coverage Gate V1 Summary

Full output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1`

Final report:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/reports/FINAL_CANDIDATE_COVERAGE_GATE_REPORT.md`

This is a VLM-defined pseudo-oracle development experiment. Conservative VLM full-scan labels were used only for evaluation. No human audit package, new VLM inference, or learned proxy training was run.

Decision: `WEAK GO`.

Reason: non-learned cheap candidate primitives show useful complementarity and improve reachable pseudo-event coverage in some K/gap settings, but gains are not strong across macro/tail source-video coverage and remain source-concentration sensitive.
