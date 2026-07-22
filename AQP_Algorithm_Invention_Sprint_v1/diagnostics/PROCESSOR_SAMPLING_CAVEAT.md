# Processor sampling caveat

## Observed evidence

The frozen runner decoded and hashed the preregistered frames (median 121.0 decoded frames per enumeration input and 21.0 per dense calibration). During the first processor invocation, Transformers emitted: "Asked to sample `fps` frames per second but no video metadata was provided ... Defaulting to `fps=24`." This message is preserved in `physical/logs/tmux_run.log`.

The installed frozen Qwen3-VL video processor computes `int(total_frames / metadata.fps * requested_fps)` and clamps to at least four frames when metadata are absent. Thus the decoded 21-frame dense input is reduced to four model-consumed frames and a 121-frame nominal enumeration input to ten. Median input-token counts were 1750 and 3528, respectively.

Post-hoc diagnostics found 51 reported enumeration fragments, of which 11 survived the preregistered midpoint owner rule. The largest reported local end time was 8.000 seconds in a nominal 60-second prompt. This is consistent with the processor constructing timestamps on the short default-24-fps interpretation, and it exposes localization/ownership failure rather than silently rescaling outputs.

## Derived conclusion

The model-consumed temporal density was not the 2 fps assumed by the simulator, even though the runner's decoded-frame identity and the message field were frozen at 2 fps. The same behavior reproduced the strict dense oracle (including byte-identical calibration responses), so benchmark comparability is retained, but the headroom model did not anticipate this physical error mode. This is a material implementation caveat and a plausible competing explanation for any accuracy failure.

## Decision consequence

No post-freeze repair, retry, or second prompt was run. A future experiment must freeze explicit `VideoMetadata` and verify post-processor frame indices before its first call; it is a new experiment, not a reinterpretation of this result.
