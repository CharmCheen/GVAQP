# Realcartest VLM-defined held-out reference recovery and corrected EVENT_ENUMERATE v2 gate

## Exact decision

`REALCARTEST_VIDEO_IDENTITY_BLOCKED`

Scope: `VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`. The reference is not human ground
truth and carries no real-world semantic-accuracy claim.

The historical 399-call runner and video inventory identify the response
source as `try_or_no/videos/realcartest.mp4`, duration `3987.104` seconds,
24.000002 FPS, 95,690 frames, 1920x1080. Those canonical bytes are absent.
The only present realcartest-named video is `realcartest_5k.mp4`, duration
208.333333 seconds and 5,000 frames. A historical session log states that it
was cut from the first 5,000 frames of `realcartest.mp4`; it is therefore a
documented prefix, not an unrelated video. Exact parent-child frame equality
cannot be recomputed without the parent bytes. The prior corrected-operator
audit records the long parent as missing and the prefix as lacking a complete
VEPC reference.

Consequently, all 399 responses cannot be bound to the present prefix's bytes
or timeline: only the first 21 ten-second windows fit within 208.333333
seconds, while the requested binding spans 3987.104 seconds. The identity stop precedes exposure, oracle binding,
reference reconstruction, processor verification, sample freezing, and
physical inference. Physical calls are zero; semantic quality and cost are
not measured; VERA physical viability remains unresolved.

Independent review: `PASS_WITH_MATERIAL_CAVEATS` after correction. It confirmed
the stop decision, required recognition of the prefix-lineage evidence, and
noted that zero-call evidence is bundle-local.

## Exact next action

Restore the exact original `try_or_no/videos/realcartest.mp4` bytes, or provide
a preserved source hash/frame manifest that can establish content equivalence
to another available 3987.104-second copy. Do not rename or stretch
`realcartest_5k.mp4`; its duration and recorded provenance contradict the
399-response timeline.
