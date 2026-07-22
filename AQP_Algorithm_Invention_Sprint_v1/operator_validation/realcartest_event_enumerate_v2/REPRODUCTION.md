# Reproduction

From the project root, verify the identity stop without model loading:

```bash
test ! -e try_or_no/videos/realcartest.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1 try_or_no/videos/realcartest_5k.mp4
sha256sum try_or_no/videos/realcartest_5k.mp4
rg -n 'VIDEO_PATH|3987.104' test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/scripts/run_full_center10_oracle.py
```

After sealing, use `FILE_MANIFEST.csv` for read-only bundle verification. The
manifest excludes itself to avoid a circular hash.
