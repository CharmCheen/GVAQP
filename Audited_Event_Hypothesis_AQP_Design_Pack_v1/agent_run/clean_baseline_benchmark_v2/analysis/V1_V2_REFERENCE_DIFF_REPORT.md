# V1 to V2 Reference Diff

Observed evidence:

- v1 reference events: 27
- v2 reference events: 27
- unchanged: 27; added: 0; removed: 0; changed: 0
- unit 346 raw response changed: True
- unit 346 parsed label: `negative` -> `negative`
- unit 346 parsed boundaries changed: False

Conclusion: `reference_changed=false`. The reference was reconstructed from all 347 v2 observations; it was not copied from v1. The identical semantic rows are a derived consequence of the unchanged parsed unit-346 label/boundaries, not reuse of the v1 evaluator artifact.
