# Full-Grid Compute Approval Template

Status: `TEMPLATE_ONLY_NOT_APPROVAL`

Exact execution seal SHA-256:
`5136aaddfc5e7daee691c9faaab323f3159db6d52a469fade45fce6719847134`

This template does not authorize execution. A valid approval artifact must bind
the exact seal, review bundle, final package manifest, 1,475 calls, 16.097123
A100 GPU-hour estimate, 19.4 A100 GPU-hour envelope, three frozen two-GPU
workers, exactly three model loads, zero reloads, zero retries, global
fail-stop, and complete-only reference publication.

Approval scope must explicitly exclude every downstream YOLO, replay,
conditioned-value, headroom, or controller experiment. Any binding change
requires a new seal, independent review, and approval.
