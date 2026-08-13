# P1 independent human reference package

This is the frozen, blinded six-cluster (three videos × two queries) human
temporal-event reference for P1. It is independent of C0/C1/K3, oracle labels,
proxy scores, selection traces, and all method results.

## Annotation procedure

1. From the repository root, launch `python scripts/serve_p1_human_reference.py`.
2. Open `http://127.0.0.1:8766/` directly in a local browser. If testing with
   command-line HTTP tooling in this environment, bypass `ALL_PROXY`, e.g.
   `curl --noproxy '*' http://127.0.0.1:8766/api/cases`.
3. Have `annotator_1` independently complete every one of the six cases using
   the frozen definitions shown in the UI. Then have `annotator_2` independently
   complete the same six cases; they must not see the first annotator's labels.
4. Preserve `HUMAN_EVENT_LABELS.jsonl` unchanged. It is append-only: a later
   save from the same annotator and case is treated as that annotator's revision.
5. Run `python scripts/finalize_p1_human_reference.py prepare-adjudication`.
   An adjudicator completes the resulting `ADJUDICATION_TEMPLATE.csv`, saves it
   as `ADJUDICATED_EVENTS.csv`, then runs
   `python scripts/finalize_p1_human_reference.py freeze`.

Do not alter query definitions, source videos, or the label log after
adjudication begins. The freeze command refuses incomplete case coverage or
missing provenance.
