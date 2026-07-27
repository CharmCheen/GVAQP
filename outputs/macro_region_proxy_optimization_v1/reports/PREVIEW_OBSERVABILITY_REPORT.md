# Preview Observability Report

Both legal P0 configurations were executed over both complete source videos and independently repeated. Feature hashes match for both configurations. Each covers all 229 regions with zero zero-sample regions and zero missing feature cells.

Selected operator: `P0_KEYFRAME_5S_160X90`, 0.2 Hz, 160×90, no DNN. Deployed wall-clock is 55.446 s, 2.892% of measured full SCAN. Its run-1 decomposition is 54.152 s decode/pipe wait, 0.000 s model, and 1.214 s feature compute; measured rate is 21.866 s per video-hour. Peak memory is a process-lifetime high-water mark of 145316 KiB, not an isolated child-process peak.

Selection used temporal support subject to the 10% ceiling and did not inspect event labels. Full-SCAN caches, tracker outputs, references, and candidate-event mappings are absent from preview inputs.
