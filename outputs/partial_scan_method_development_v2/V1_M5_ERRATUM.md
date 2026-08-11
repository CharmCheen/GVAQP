# V1 M5 Interpretation Erratum

The frozen V1 files and numbers are retained unchanged. Review of the M5 code
found that its macro activity score summed candidate scores from unscanned
units. That is future-observation lookahead and is incompatible with the stated
online policy semantics.

Consequently, V1 M5 is retained only as a failure-detection artifact, not as
evidence that online macro-region activity is effective. V2 reruns the question
using scores derived exclusively from completed scans.
