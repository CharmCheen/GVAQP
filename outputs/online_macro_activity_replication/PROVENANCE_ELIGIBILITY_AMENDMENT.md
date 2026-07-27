# Provenance Eligibility Amendment — Owner Attestation

This amendment changes only Phase-A admissible provenance evidence. It does
not change video selection order, video bytes, timelines, SCAN, reference
construction, candidate-event matching, activity features, shrinkage, budget,
seeds, metrics, gates, or confirmatory methods.

```text
ACCEPTABLE_PROVENANCE_EVIDENCE =
    ORIGINAL_DATASET_MANIFEST
    OR SOURCE_PROVIDER_DECLARATION
    OR PROJECT_OWNER_ATTESTATION

OWNER_ATTESTATION_REQUIREMENTS =
    named declarant
    declaration date
    explicit continuity statement
    explicit non-trimming statement
    explicit non-event-selection statement
    explicit session-independence statement
    video hash binding

INDEPENDENT_WEB_VERIFICATION =
NOT_REQUIRED_WHEN_VALID_OWNER_ATTESTATION_IS_PRESENT
```

`PROJECT_OWNER_ATTESTATION` establishes project-local provenance only. It must
not be reported as third-party platform verification. It is invalidated by any
change to the bound video SHA-256.
