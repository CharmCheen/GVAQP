# Oracle Protocol

Reference source: V13.8 Qwen3-VL-32B full center10 pseudo-oracle labels on `realcartest`.

No new large VLM full scan was launched for this experiment. The mini-universe full reference is a
clean, clipped, 2s-unit rematerialization of the selected V13.8 pseudo-oracle event intervals.

Predicate: `O_enter_ego_path_v0`, an object starts outside the ego future path and enters or overlaps
it, creating potential spatial conflict requiring ego attention.

Oracle replay policy: limited-budget methods may query only this rematerialized reference through the
oracle replay lookup, which returns whether the queried interval contains any positive 2s base unit.
Event-level IoU hits are reserved for final evaluation. Unqueried labels are not available to
calibration, proposal generation, or optimization.
