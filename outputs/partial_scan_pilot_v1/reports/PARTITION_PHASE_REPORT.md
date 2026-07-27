# Partition Phase Report

Formal offset=0 and sensitivity offset=5 were scanned independently.

Audit status: `PASS`.

```json
{
  "formal_partition": "offset0",
  "sensitivity_partition": "offset5",
  "status": "PASS",
  "thresholds_frozen_before_evaluation": true,
  "videos": [
    {
      "REFERENCE_EVENT_EXPOSABLE_OFFSET_0": 70,
      "REFERENCE_EVENT_EXPOSABLE_OFFSET_5": 72,
      "REFERENCE_EVENT_TOTAL": 72,
      "REFERENCE_EVENT_UNEXPOSABLE_AT_BOUNDARY": 2,
      "REFERENCE_EVENT_UNEXPOSABLE_OTHER": 0,
      "boundary_unexposed_ids": [
        "PSP_V0_SHORT_ref_0017",
        "PSP_V0_SHORT_ref_0020"
      ],
      "materially_lower_threshold_absolute": 0.1,
      "minimum_engineering_ceiling": 0.5,
      "offset0_ceiling": 0.9722222222222222,
      "offset5_ceiling": 1.0,
      "other_unexposed_ids": [],
      "status": "PASS",
      "video_id": "PSP_V0_SHORT"
    },
    {
      "REFERENCE_EVENT_EXPOSABLE_OFFSET_0": 193,
      "REFERENCE_EVENT_EXPOSABLE_OFFSET_5": 195,
      "REFERENCE_EVENT_TOTAL": 196,
      "REFERENCE_EVENT_UNEXPOSABLE_AT_BOUNDARY": 2,
      "REFERENCE_EVENT_UNEXPOSABLE_OTHER": 1,
      "boundary_unexposed_ids": [
        "PSP_V1_LONG_ref_0076",
        "PSP_V1_LONG_ref_0167"
      ],
      "materially_lower_threshold_absolute": 0.1,
      "minimum_engineering_ceiling": 0.5,
      "offset0_ceiling": 0.9846938775510204,
      "offset5_ceiling": 0.9948979591836735,
      "other_unexposed_ids": [
        "PSP_V1_LONG_ref_0184"
      ],
      "status": "PASS",
      "video_id": "PSP_V1_LONG"
    }
  ]
}
```
