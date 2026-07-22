# A100 Resume Checkpoint Audit

## Strongest supported conclusion

The reported `75/149` checkpoint is not valid under the frozen validity rules. Filesystem evidence proves `0` `COMPLETE_VALID`: no setting has a completion marker, persisted policy/budget metrics, or an artifact manifest.

## Direct evidence

- Frozen matrix: 149 rows, 149 unique IDs.
- Seed manifest: 14850 rows; one N=1000 setting has 50 seeds, all others 100.
- Public gzip: 2805736 recoverable rows; `EOFError: Compressed file ended before the end-of-stream marker was reached`.
- Hidden gzip: 1500728 recoverable rows; `EOFError: Compressed file ended before the end-of-stream marker was reached`.
- Classification: `{"INCOMPLETE": 121, "NOT_STARTED": 28}`.

Unequal stream coverage follows from independent gzip buffers at abrupt termination and proves neither stream is complete. The partial files remain forensic evidence until equivalence is complete, then are archived rather than deleted.

## Competing explanation and uncertainty

The old process may have computed additional results in memory, but no durable artifact proves or aggregates them. The last in-memory setting is unrecoverable. Recomputing settings without a valid durable checkpoint is required and does not restart a `COMPLETE_VALID` setting.
