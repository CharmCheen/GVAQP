# Failure Analysis

Q1-L was deterministic and cheap but missed the Recall@20 threshold on both
videos. Q2 falsified the “insufficient detection sampling” explanation: its
selected high-rate YOLO features did not strictly improve Q1 on either video.
Q3 tested a materially different signal; directional residual flow produced a
small long-video-only improvement and no short-video improvement.

The strongest negative evidence is cost-adjusted: Q2 at 20% total budget was
-3/+7 events and Q3 was -5/+1. A macro average could hide the short-video
failure, so both were rejected. No scheduler replay or new physical runs were
performed because doing so after the static Gate failed would test a mechanism
whose input value is not established.

Unresolved: only two design videos exist, event truth is a frozen Oracle
pseudo-reference, and no independent validation/test videos exist. A future
branch should begin with additional complete videos or a new preregistered
longer-context observable, not more tuning of Q2/Q3.
