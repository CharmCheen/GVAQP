# ANY/COUNT consistency rules

Safety precedence is `UNKNOWN > POSITIVE > advisory COUNT` for pruning.

- ANY POSITIVE with COUNT 0: split/localize; record contradiction.
- ANY UNKNOWN with any COUNT: safe fallback; COUNT may only order fallback.
- ANY NEGATIVE eligible for pruning with COUNT >0: contradiction becomes
  UNKNOWN; do not prune.
- ANY NEGATIVE eligible with COUNT 0: pruning allowed only if all other ANY
  completeness/provenance conditions pass.
- Event-list length mismatch, duplicates, boundary truncation or localization
  outside the target never changes the safe ANY fallback.
