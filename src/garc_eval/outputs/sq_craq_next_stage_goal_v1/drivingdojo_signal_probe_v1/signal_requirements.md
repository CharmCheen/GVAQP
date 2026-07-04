# Signal Requirements

DrivingDojo should be used as a signal-design corpus, not as the final AQP benchmark. The needed signal is answer-compatible: it must separate intervals that answer `O_enter_ego_path_v0` from high-score hard negatives inside the same candidate bin.

Candidate signal families:
- track-level interaction
- lateral displacement
- bbox center trajectory
- bbox area expansion
- object enters ego-center region
- multi-object proximity
- temporal consistency
- inside-outside contrast
- boundary sharpness
- hard-negative suppression
