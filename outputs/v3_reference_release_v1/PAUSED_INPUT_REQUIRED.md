# V3 Reference Release Paused

## Exact blocker

The sealed V7 worker rejects the current processor environment before inference: the frozen `transformers`, OpenCV, and NumPy identities do not match.  In addition, V3 selector-facing scan candidate/proxy tables have not been executed or released.

## Why it matters

Using a substituted runtime would change frozen reference semantics; using V5 partial raw labels would violate V7's explicit fresh-execution and non-reuse policy.  Without candidate/proxy tables P0 cannot form a common selector-visible universe.

## Minimum user action

Make the exact frozen processor runtime available, then authorize/use the already preregistered frozen V3 scan/proxy execution configuration. No model, prompt, unitization, parser, or K3 configuration change is required or authorized by this package.
