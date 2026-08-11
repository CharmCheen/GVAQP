# Reference Circularity Audit

Status: `QUALIFIED_NOT_YET_GATEABLE`.

The intended evaluator-side reference is constructed in two stages: complete
Qwen unit outcomes define the model-relative unit-level semantic reference,
then `K3UnitEventAdapter` materializes an evaluator-side event relation. A
future method-side materializer will consume only a sparse selector query
trace. Those inputs and roles are distinct.

However, if a method-side variant uses the same deterministic K3 rule as the
evaluator-side event construction, event-level agreement can partly reflect a
shared materialization inductive bias rather than independent semantic-event
ground truth. This is a limitation for a K0-versus-K3 ablation, not evidence
of K3 superiority. Any later P0 protocol must state this model-relative
construction and retain unit-level outcome diagnostics/sensitivity analysis.

No final circularity gate can pass yet: the prospective scan/proxy tables and
the complete V7 full-grid unit-label relation do not exist. No method-side
K3, K0, selector trace, or Event-F1 was executed for this audit.
