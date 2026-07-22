# Reproduction

Run from the project root:

```bash
test -d data/realcam/heldout_v1/raw
find data/realcam/heldout_v1/raw -type f -print
sha256sum data/realcam/long_video_data/long_video_dataset3.mp4
```

For the recorded state, the first command exits nonzero, the `find` command
reports that the directory does not exist, and the strict-video SHA256 is
`bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`.

No model, EVENT_ENUMERATE, VERA, semantic annotation, or physical inference is
needed to reproduce the terminal decision.
