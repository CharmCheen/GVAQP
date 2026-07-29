# V3 Full-Grid Proposal Independent Review V1

Reviewed proposal JSON SHA-256:
`21bf20d5bf72565e31f9419cce8cce216bc69aa82ef6ef3c1b263ce3b85ba859`

Reviewed proposal document SHA-256:
`d9b901b12da5916abfc01c1504175f7421508f9fa83036152415ebd24b62fbe9`

Decision: `REVISE_FULL_GRID_PROPOSAL`

The independent adversarial review verified the exact `567 + 561 + 347 =
1,475` call count, the 16.097123 A100 GPU-hour estimate, the 3.093181-hour
maximum parallel wall time, the 19.4-hour planning envelope, and the proposed
12/2/6 truncated-final-unit frame counts. It found four hard blockers:

1. The proposal cited the current `ModelRelativeLabelStore.controller_view()`
   as a label-hiding boundary even though that method returns a label for any
   caller-supplied unit ID. It does not authenticate a causally completed
   VERIFY action and therefore cannot establish the required hiding invariant.
2. The three-load cost assumed uninterrupted shard processes while the resume
   text permitted a process restart without an explicit reload budget,
   checkpoint-load ledger, or cost-stop rule.
3. Failure behavior across three concurrent shards did not choose a frozen
   global or shard-local stop rule.
4. K3 publication from “all available” outcomes did not forbid an incomplete
   or missing-label relation from being published as the authoritative full
   reference or used downstream.

The tail-unit rule itself is acceptable at proposal stage, but implementation,
decode/no-overrun tests, exact frame hashes, and the full call/frame manifests
remain mandatory before preregistration and seal. No model inference or input
expansion was performed by this review.
