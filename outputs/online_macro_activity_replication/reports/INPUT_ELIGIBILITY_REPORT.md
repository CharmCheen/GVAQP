# Input Eligibility Report

`CONFIRMATORY_EXECUTION_STATUS = PAUSED_INPUT_REQUIRED`

The three requested provenance declarations and hash-bound owner attestations
are present. `杭州.mp4` is individually technically executable under
`PROJECT_OWNER_ATTESTATION`; it is not a qualified member of a two-video
confirmatory set because direct blind content evidence contradicts independence
from `杭州YouTube.mp4`.

`杭州YouTube.mp4` fails original full decode. Its container-level remux also
fails full decode. The one allowed technical transcode yields 473.7 seconds
from a 5600.566-second input (91.54% timeline loss), so it fails
`NO_UNEXPLAINED_TEMPORAL_GAPS` and cannot replace the original.

No held-out reference, Oracle event result, candidate-event mapping, event
count/density, B0/A1/A2/A3/A4 result, or method metric was opened or run.
One new, technically valid and content-independent confirmation video is still
required; because the current Hangzhou pair has direct same-content evidence,
the provided second asset cannot satisfy that role.
