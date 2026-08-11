# Full-Grid Compute Approval Template

Status: `TEMPLATE_ONLY_NOT_APPROVAL`

Exact execution seal SHA-256:
`ca10897d0ca4ac6870b7db2a3b5d5ba383c5d2639ab49426f1f60c9d8580c3a9`

This template does not authorize execution. A valid approval artifact must bind
the exact seal, review bundle, final package manifest, 1,475 calls, 18.835258
A100 GPU-hour estimate, 56.0 A100 GPU-hour envelope, three frozen two-GPU
workers, exactly three model loads, zero reloads, zero retries, global
fail-stop, and complete-only reference publication.

This is a new execution from unit zero. It deliberately re-executes units from
the preserved failed run under the expanded user authorization, while reusing
none of their labels. Zero retries means zero retries within this fresh seal.

This exact artifact governs only the fresh complete full-grid execution. The
user's separate expanded authorization governs downstream work after a formal
reference release. Any binding change requires a new seal and independent
review.
