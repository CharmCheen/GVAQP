# Boundary / REFINE Feasibility Audit

Based on `BOUNDARY_DEGENERACY_AUDIT.md` (P1), `STAGE1_BOUNDARY_FIX_SMOKE.md` (S1), `analysis/stage1_boundary_scheme_comparison.csv`, `full_center10_analysis.json` (boundary_unique_starts/ends).

---

## Q1: Does P1 boundary degeneracy still exist?

**YES, and it's worse in the full scan.** 

P1: All 5 positives have event_start=0.0, event_end=0.7.
Full scan: All 40 positives have event_end=0.7. Most have event_start=0.0, a few have 0.5.

Boundary status from `full_center10_analysis.json`:
- Unique event_start values: 2 (0.0, 0.5) — only +1 from P1
- Unique event_end values: 1 (0.7) — identical to P1

## Q2: Which boundary fix is most effective?

**None of the three schemes fully solves the problem.**

| scheme | label match | boundaries | used for full scan? |
|---|---|---|---|
| A (video metadata fix) | 93% | still templated | YES (best label stability) |
| B (contact sheet) | 79% | varied (4 unique) | NO (degrades label quality) |
| C (post-hoc) | incomplete (3/5) | varied (2 unique) | FUTURE (needs more testing) |

**Key finding from Scheme A:** Even with `raw_fps=30` passed to `fetch_video`, the VLM still produces templated boundaries (0.0-0.7). This is NOT a metadata issue — it's a VLM behavior for the video input format.

**Key finding from Scheme B:** Contact sheets produce diverse boundaries (4 unique event_end values) but at the cost of missing a genuine positive (0060) and hallucinating a false positive (0231). The tradeoff is unacceptable for the AQP contribution.

**Key finding from Scheme C:** Post-hoc boundary queries with explicit before/during/after prompts produce varied boundaries (0.0-0.5, 0.5-1.0) but require a SEPARATE VLM call per anchor and had parse errors on 2/5 anchors.

## Q3: Do event_start/event_end have usable variation?

**NO, with the current VLM/video format.** 

All 40 positives have event_end=0.7 (zero variation). Two values of event_start (0.0 and 0.5) — the 0.5 may be a real variation but it's indistinguishable from rounding noise given that 39/40 are 0.0.

## Q4: Is boundary evidence credible?

**NO.** 

- `boundary_status` = "ok" for all anchors — not credible when all boundaries are identical
- `complete_event_visible` = True for all — improbable given that some clips capture only the tail of an event
- Without temporal grounding, the VLM's boundary estimates are not usable

## Q5: Can boundary fields be used for event IoU?

**NO.** Boundary fields are templated. Event IoU would be meaningless (all events would have IoU=1.0 with event_end=0.7).

## Q6: Can REFINE be a core innovation?

**NO — with the current evidence strength.**

REFINE (boundary refinement) is:
1. **Not needed for clip-level recall** — the AQP contribution is binary anchor-level positive/negative
2. **Not solved** — three schemes tested, none fully work
3. **Potentially distracting** — pursuing boundary refinement diverts from the core AQP story (budget allocation + recall guarantee)
4. **A post-hoc engineering step** — not a contribution suitable for VLDB/SIGMOD/ICDE

## Q7: REFINE current evidence strength

**WEAK — unsupported for core contribution.**

| criterion | evidence | rating |
|---|---|---|
| Boundaries varied across events | NO (all templated) | ✗ |
| Refinement improves precision | NOT TESTED | ? |
| Refinement preserves recall | NOT TESTED | ? |
| Refinement is reliable across scenes | NOT TESTED | ? |
| Refinement is computationally cheap | needs extra VLM call | ✗ |

## Q8: Fallback for clip-level AQP when REFINE is unstable

**Anchor-level result construction.** The current approach:
- Merge adjacent positive anchors into event clusters
- Report cluster-level results with VLM evidence
- Do NOT report precise boundary-localized events
- Quality statement: clip-level recall on center10 anchors, not event-stitched boundaries

**This is already the design in the DCA algorithm** — the method operates on anchor labels, not boundaries. Event stitching is anchor-level adjacency, not boundary-level localization.

## Q9: Minimum validation experiment for REFINE

**E5: Post-hoc boundary refinement on all 40 positives.**

If we wanted to pursue REFINE:
1. Run Scheme C on all 40 positives (40 VLM calls, ~10 min GPU)
2. Check if varied boundaries emerge (at least 5 unique values)
3. If boundaries are still templated → ABANDON boundary refinement
4. If boundaries are varied → compare to anchor-level event stitching, see if boundary-level events give different clusters

**Recommendation:** Do NOT prioritize E5 until DCA validation (E1) and certificate simulation (E3) are complete.

---

## Final Assessment

**Boundary is NOT a core contribution opportunity.** It is a known limitation. The AQP contribution should be built on **clip-level anchor labels** (which are reliable: 100% parse, 0% abstain, 93% stability) and should frame boundary refinement as future/limitation work, not as a claimed contribution.
