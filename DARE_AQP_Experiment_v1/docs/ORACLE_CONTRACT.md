# Pilot oracle contract

## Status

This contract is a **working experimental definition** for the frozen
VLM-defined pseudo-event population.  It is not evidence that the same
operations are available or reliable for real human events.

## Population

- `Unit`: one of 347 frozen 10-second temporal units.
- `PseudoEvent`: one of 26 reference runs of consecutive positive units.
- `CanonicalAnchor(event)`: the unit containing the frozen
  `canonical_anchor_time` (the first positive unit in v1).

The checked input has 26 distinct canonical-anchor units, so the residual
anchor variable is binary at unit resolution.

## Operations and pilot costs

### `PresenceOracle(unit) -> {positive, negative}`

Returns positive iff the unit is listed in at least one pseudo-event's
`source_unit_ids`.  Cost: one logical unit query.

### `CertifyEvent(seed_unit) -> event_id, anchor_unit, source_units`

For a positive seed, returns the unique frozen pseudo-event identity, its
canonical anchor, and its pseudo-event source units.  Cost: one logical
certification call per newly found event.  This is an evaluator-backed replay
operation; a real typed oracle has not been implemented.

### `AuditUnit(unit) -> residual_anchor_indicator, event_identity_if_positive`

Independently samples a unit with a registered inclusion design and completely
checks whether it is the canonical anchor of an event not already certified by
discovery.  A positive complete audit also returns the pseudo-event identity;
its registered unit cost includes that identification, so it does not incur a
second `CertifyEvent` charge.  This differs from the cheaper discovery presence
operation and is an explicit pilot cost assumption.

The dense comparator executes `AuditUnit` on all 347 units and therefore has
the same event-identifying output semantics.  With the v1 unit costs it costs
347 logical calls.  Real measurements must replace the assumed equal unit
costs before making a wall-clock acceleration claim.

## Independence and leakage boundary

Discovery sees only public proxy values plus results of its own presence and
certification calls.  Audit uses a separate random stream.  Reference events
are used by the simulator to realize oracle responses and by the evaluator;
they are never used to rank proxy-top discovery.

## Non-identifiable real-world assumptions

The pilot assumes that certification can uniquely identify an event and its
anchor.  Binary presence labels alone do not establish actor identity or event
identity.  Before any real-event recall claim, this contract must be replaced
by a human-adjudicated schema with anchor agreement and measured costs.
