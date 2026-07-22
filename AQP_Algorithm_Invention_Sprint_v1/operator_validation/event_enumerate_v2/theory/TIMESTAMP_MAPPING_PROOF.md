# Timestamp mapping proof

## Definitions

Let a source video have FPS `f > 0`.  For an input interval, the frozen sampler
selects strictly increasing source-frame indices

```text
s_0, s_1, ..., s_(n-1).
```

The real timestamp of selected frame `i` is `r_i = s_i / f`.  Define the
absolute anchor `a = r_0` and metadata offsets `d_i = s_i - s_0`.  The v2
processor receives `fps=f`, `frames_indices=[d_i]`, and
`do_sample_frames=False`.

## Lemma 1 — frame timestamp identity

The metadata-derived timestamp for selected frame `i` is

```text
d_i / f = (s_i - s_0) / f = r_i - a.
```

Adding the anchor recovers the exact decoded source timestamp:

```text
a + d_i/f = s_0/f + (s_i-s_0)/f = s_i/f = r_i.
```

Thus a nonzero absolute input offset and a non-integral reported source FPS do
not change temporal scale.

## Lemma 2 — temporal-patch identity

The installed Qwen3-VL processor groups two frames per temporal patch.  For a
pair `(i,j)` it writes timestamp

```text
p_(i,j) = (d_i/f + d_j/f) / 2.
```

Adding `a` gives

```text
a + p_(i,j) = (r_i + r_j) / 2,
```

the exact midpoint of the two decoded source-frame times.  If `n` is odd, the
processor repeats `d_(n-1)`; the final patch time is exactly
`d_(n-1)/f`, so no phantom half-frame is introduced.

## Lemma 3 — relative-to-absolute output mapping

The frozen prompt defines a generated boundary `g` as seconds relative to the
sampled clip start.  The post-processor maps it to

```text
G = a + g.
```

For any boundary tied to a represented frame or patch, Lemmas 1–2 show that
`G` lies in the same real source coordinate system.  No nominal interval
boundary or target FPS enters the mapping.

## Display tolerance

Processor timestamp tokens use one decimal place.  Rounding a real timestamp
to the nearest 0.1 seconds introduces at most 0.05 seconds error.  The parser
therefore uses a frozen `0.050001`-second upper-bound tolerance only at the
right clip boundary.  It does not clamp an accepted value.  Internal exact
metadata timestamps and absolute mapping remain unrounded.

## Boundary and final-interval behavior

The end source frame is capped at `total_frames-1`.  Hence every selected real
timestamp is within the media.  A final partial interval may end at container
duration even though its last frame timestamp is one frame period earlier;
the transported duration is the actual last selected frame time relative to
the anchor.  Output beyond that duration plus display tolerance is rejected.

Ownership uses an event midpoint and half-open cores `[start,end)`, except the
last timeline core is closed on the right.  Therefore a retained event has at
most one owner, including an event whose midpoint is exactly a core boundary.

## What this proof does not establish

It proves timestamp transport and deterministic mapping.  It does not prove
that the model understands the timestamp tokens, detects the target event,
localizes semantic boundaries accurately, or meets the frozen recall/F1 gate.
Those claims require a disjoint trusted event reference, which is currently
absent.

