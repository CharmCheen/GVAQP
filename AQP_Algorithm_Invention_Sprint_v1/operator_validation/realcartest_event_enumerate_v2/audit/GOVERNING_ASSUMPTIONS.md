# Governing user-provided provenance assumptions

1. `realcartest_5k.mp4` does not overlap `long_video_dataset3.mp4`.
2. `realcartest_5k.mp4` was never read or used by VERA or the current research process.
3. Existing Qwen3-VL oracle annotations are exact under the user's AQP abstraction.
4. Any resulting reference is `VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`, not human ground truth.
5. No real-world semantic-accuracy or human-GT claim is authorized.

These provenance assumptions do not override conflicting artifact identity.
The historical runner and inventory bind the 399 responses to a missing long
parent. The present 208-second file is documented as its prefix, but cannot
support binding responses outside that prefix.
