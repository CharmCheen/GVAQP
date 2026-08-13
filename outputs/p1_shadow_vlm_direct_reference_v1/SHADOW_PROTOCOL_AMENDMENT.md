# P1 shadow infrastructure amendment 1

The initial cross-family SmolVLM2-500M judge failed before analysis: its 15-frame input exceeded the model's 8192-token context and all completed responses were schema-invalid repetitive text. The partial A/B streams were archived and excluded; both annotators restart from zero.

VLM_B is replaced by the locally frozen Qwen3-VL-32B-FP8 checkpoint. VLM_A remains Qwen3-VL-8B. This sacrifices cross-family independence but preserves distinct checkpoints and isolated sessions. The windowing, prompt, queries, blinding, stitching, pseudo-adjudication and analysis contract are unchanged. No formal P1 file was written or modified.

- Prior protocol: `bd9564ac615e14656f488fd2f4cbbb06a42f38856a131f756499e525dbcfef26`
- Amended protocol: `0447f2dc2169eb729687d0a5b0cd93b10cd0ef5929208ae5477b89dd5c6fa507`
