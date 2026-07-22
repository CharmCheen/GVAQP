# Research state

## Established

- Conditional HT unbiasedness is valid for arbitrary frozen ANY errors when
  audit inclusion probabilities are known and outcome-independent.
- Conservative SRS/stratified bounds cover in all 56,448 aggregated cells.
- No random-only or adversarially robust cell passes recall, confidence and
  cost together.
- Exact ANY itself costs 243/347, already just above the strict cost gate.
- Physical VLM calls remain zero.

## Rejected hypothesis

Independent probability auditing of provisional negative blocks does not rescue
the frozen interval route: confidence-valid auditing costs too much under full
unit audit.

## Decision and next action

`RISK_LIMITING_INTERVAL_NO_GO`. Do not define or run a physical validation
experiment for this family. Revisit only through a separately frozen change to
the physical audit primitive or cost denominator, not by assuming nicer VLM
errors.
