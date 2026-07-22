# V2 independent red-team review

```text
VERDICT = BLOCKED_REQUIRES_SCIENTIFIC_AMENDMENT
```

The frozen coverage registry has 13 rows, which with six public seeds and five
methods defines 390 identities. The legacy runner iterates exactly that matrix.
The IC1 runner instead loads those rows and appends unregistered
`ic1-cfg-13` through `ic1-cfg-18`, defining 19 rows and 570 identities; IC1
artifacts report 570. Its development-universe hash binds only the sparse seed
specification, not the effective appended identity set. Thus two compatible
executions have different same-universe obligations.

The root-world deficiency is repairable once an identity set is authorized:
the spec omits actual seed values, root objects and finite-library commitment,
although current six seeds map distinctly to worlds 209–214. V2 may not choose
between 390 and 570, so no CAS/replay materialization is authorized.
