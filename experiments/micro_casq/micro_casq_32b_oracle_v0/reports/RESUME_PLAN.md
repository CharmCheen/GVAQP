# Resume Plan

The initial 32B-oracle loop was stopped because GPU execution was suspected or unverified. Pre-repair raw outputs are preserved, but materializable rows with only pre-repair outputs are scheduled for GPU-verified rerun.

| resume_action | count |
| --- | --- |
| skip_non_materializable | 347 |
| rerun_missing_output | 103 |
| rerun_previous_error | 50 |
