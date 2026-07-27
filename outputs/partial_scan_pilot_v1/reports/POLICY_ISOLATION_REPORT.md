# Policy Isolation Report

`POLICY_INFORMATION_ISOLATION = FAIL`.

The original audit only established that `PublicScanState` omitted forbidden
fields. It did not establish an execution boundary. Policies run as unrestricted
Python in the evaluator process and can import benchmark modules and access the
filesystem.

All four required adversarial attempts succeeded:

- evaluator reference file read;
- future runtime file read;
- unscanned output-path enumeration;
- candidate-to-reference mapping read.

The acceptance rule is fail-on-any-success, so interface compatibility and the
absence of a reference loader in the shipped policies cannot rescue this gate.
No second repair was attempted because the one controlled repair cycle had
already been consumed. Frozen immutable evidence was not changed.
