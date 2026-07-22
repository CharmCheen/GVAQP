# Realcartest identity report

Status: `FAIL_MISSING_CANONICAL_BYTES`.

Recursive filename search found one realcartest-named media file:
`try_or_no/videos/realcartest_5k.mp4`. Its entire 5,000-frame decode succeeded;
the aggregate of per-frame decoded BGR SHA256 digests is
`28a906610851d5e6f90eaf0425a446fea302d6e3965f6cb2ee7c1a64c2355336`.

The historical session log reports this artifact was cut from the first 5,000
frames of the long source. That supports prefix lineage, although exact frame
equality cannot be recomputed because the parent bytes are absent. It cannot
establish complete identity with the 399-response source. The historical
runner hard-codes `try_or_no/videos/realcartest.mp4`; the historical inventory
assigns that video duration 3987.104 seconds and 95,690 frames, while assigning
`realcartest_5k` its own artifact ID, 208.333333 seconds, and 5,000 frames.
Only the first 21 grid windows lie within the prefix. Response intervals beyond
208.333333 seconds make all-399 binding impossible. No complete canonical
response-source video is assigned.
