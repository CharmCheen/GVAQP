# H7 Annotation Package Status

- **Existing exhaustive subset**: not found
- **Generated annotation package**: yes
- **Template path**: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_h7_long_event_v1/h7_annotation_template.csv`
- **Windows included**:
  - window_high_prior: bins 0-18, 180s
  - window_low_prior: bins 102-120, 180s
  - window_suspected_leakage: bins 76-94, 180s
- **Action required**: human annotators must fill the `label` column for every bin.
- **H7 status**: pending human annotation

## Window selection rationale
- window_high_prior: high-prior region where audit ledger is expected to estimate p_in accurately.
- window_low_prior: low-prior region where audit ledger estimates p_out and outside-envelope leakage.
- window_suspected_leakage: region around a known long event partly outside top30 E0; used only for H1/H2 qualitative evidence, not for H7 calibration.

## Label distribution guideline
- Every bin in window_high_prior and window_low_prior must have a label.
- Use `uncertain` when the scene cannot be confidently classified; do not default to `negative`.
- Fill `event_fraction_in_bin` when a positive event only partially occupies the bin.
