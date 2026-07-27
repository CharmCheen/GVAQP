# Exact input request

Provide at least **three additional** mutually independent, complete forward-facing road videos. Each must be at least 1,200 seconds (1,800 seconds recommended), come from a distinct non-overlapping capture session, and not be a crop, split, overlap, reencode, or derivative of any existing source.

Place each video in `data/realcam/selected_frontier_calibration_inputs/` with a sibling `<filename>.source.json` containing the fields frozen in the contract, including an immutable `registration_utc`, unique `capture_session_id`, provenance, parent/derivation declarations, and `target_event_information_used_for_selection=false`. Do not select or replace inputs based on event density or model behavior.

After receipt, rerun only the technical/provenance input gate. Oracle work still requires the four-video gate, frozen role/hash assignment, and explicit compute authorization.
