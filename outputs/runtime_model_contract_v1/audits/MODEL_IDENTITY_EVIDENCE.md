# Runtime model identity evidence

SOURCE_REPOSITORY_REQUESTED: /qiuyeqing/llama_prl/G-ARC
SOURCE_REPOSITORY_USED: /tmp/garc_runtime_contract_source (local repository /root/charm/GVAQP, exact commit, remote differs)
SOURCE_COMMIT: 5047241b0561b911b9a519b18e8e7591c0074e70

- YOLO: `yolov8n.pt`; formal proxy code uses Ultralytics; SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.
- VLM: `Qwen3-VL-32B-Instruct`; the tracked physical model manifest records content hash `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`.
- Earlier `test_vlm` Qwen3-VL-8B references are test/legacy evidence and do not override the formal physical chain.
- HF revision `0cfaf48183f594c314753d30a4c4974bc75f3ccb` was accepted only after all available small files matched the source manifest byte-for-byte.
