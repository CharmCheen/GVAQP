# V2 Interrupted-Run Recovery Report

Replay and Physical runners share marker-gated destination preparation.

A destination can be removed only when it is a strict child of the appropriate
V2 run root, is not the root itself, has no `run_summary.json`, and contains
`.partial_scan_incomplete_run`. Each permitted removal appends an entry to
`outputs/partial_scan_pilot_v2/repair_log.json`. Completion removes the marker
and then atomically writes `run_summary.json`.

Constructed temporary-directory tests passed for a new destination, a valid
incomplete destination, a completed destination, a destination outside its
root, the root itself, and a directory without the marker.

`INCOMPLETE_RUN_RECOVERY = PASS`
