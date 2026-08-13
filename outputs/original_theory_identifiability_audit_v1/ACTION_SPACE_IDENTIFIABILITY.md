# Action-space identifiability

The actual environment is internally partially observable: unscanned proxy values are absent from public state and VERIFY is illegal until the unit's cell is scanned. SCAN expands the legal VERIFY frontier. However, constructor inputs contain complete unit/proxy/oracle maps; SCAN performs a lookup, uses constant abstract cost 0.1, reads no raw video, runs no cheap model, and creates no candidate identity. VERIFY costs abstract 1.0 and reveals a cached model-relative label. Branches alter future released subsets but not the cached observation-generating process; all use one fixed continuation.

`ORIGINAL_SCAN_VERIFY_PROBLEM_IDENTIFIED = PARTIAL`

Faithfully identified: delayed proxy visibility, legal frontier gating, asymmetric abstract costs, verified feedback, and one-step terminal continuation. Not identified: online sensing, natural exposure failure, endogenous candidate creation, measured physical costs, policy-induced sensing outcomes, human-valid utility, and natural closed-loop state prevalence.

Across the 108 audited forced-SCAN branches, the semantic decomposition is: new raw observation `0/108`, online proxy computation `0/108`, new artifact candidate identity `0/108`, release of precomputed proxy/candidate evidence `108/108`, and expansion of future legal VERIFY actions `108/108`. Thus SCAN is more than order-only bookkeeping, but less than endogenous sensing.
