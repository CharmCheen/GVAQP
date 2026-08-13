# P1-B blinded human-reference package

1. From the repository root run `python scripts/serve_p1_independent_geometry_reference.py` and open `http://127.0.0.1:8767/`.
2. ANNOTATOR_A completes all six cases. ANNOTATOR_B independently completes the same six using the frozen guide. Do not exchange event locations.
3. Each case must be saved, including an explicit empty event list for no-event. Saves append revisions and never overwrite the raw log.
4. After both finish, run `python scripts/resume_p1_independent_geometry_replication.py --check`, then run it without flags. This validates all 12 case submissions and computes agreement only; it does not open method outcomes.
5. Only if the preregistered reference-quality gate passes, fill the generated `ADJUDICATION_TEMPLATE.csv` as `ADJUDICATED_EVENTS.csv`. The adjudicator remains blinded to all algorithmic artifacts. Run the resume script again to freeze the reference and execute P1.

Normal annotation mode must expose only raw video, query text, clock, guide, and annotation controls.
