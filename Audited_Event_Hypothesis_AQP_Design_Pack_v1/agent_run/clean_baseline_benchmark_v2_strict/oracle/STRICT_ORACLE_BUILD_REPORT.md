# Strict Benchmark v2 Oracle Build Report

- Status: `COMPLETE_COMMITTED`
- Oracle-build ID: `strict_oracle_3b9ba1187c0449426978`
- Units: 347
- Accepted durable fresh outputs: 347
- Physical attempts started (upper bound if interrupted): 347
- Exact physical generate invocations: 347
- Uncertain interrupted attempts: 0
- Legacy raw responses reused: 0
- Parse failures/invalid labels: 0
- Full model-content hash: `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`
- Model file manifest SHA256: `a27032176f0193562426fed825fc8822f6a8f562c83383f5ba9aab2e7aae1d00`
- Prompt SHA256: `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`
- Generation-config hash: `7b0ad9bafb6ab198e30909c0f4caa1c68a089a63029d51fad1d1eb3889188375`
- Input-identities SHA256: `48c513e121f1df2d43d64586d9936de937080585258a062facd5ba735420351e`

Every raw response was atomically saved before parsing. Each call binds the
full model-file content manifest, prompt, parser, sampler, decoded frame
indices/content, explicit greedy generation configuration, and per-unit RNG
identity. Existing output reuse is allowed only to resume this exact strict
oracle-build ID and exact input identity.
