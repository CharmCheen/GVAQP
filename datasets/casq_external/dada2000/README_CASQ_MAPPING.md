# DADA-2000 / LOTVS-DADA CASQ Mapping

## Expected Raw Files

- RGB videos or extracted frame sequences under `datasets/casq_external/dada2000/raw/` or `datasets/casq_external/dada2000/frames/`.
- Optional attention maps or semantic images if needed for later analysis, but Phase 1 ingestion does not require them.

## Expected Annotation Files

- `datasets/casq_external/dada2000/annotations/accident_intervals.csv`
- or `datasets/casq_external/dada2000/annotations/accident_intervals.json`
- Optional local CASQ-ready file: `datasets/casq_external/dada2000/annotations/casq_event_boundaries.csv`

The public LOTVS-DADA GitHub repository includes split files such as `train_file.json`, `val_file.json`, and `test_file.json`, but those files list sequence identifiers rather than clean event boundaries. The paper/documentation reports accident intervals, so the actual interval annotations must be obtained and inspected from the dataset release before conversion.

## Event Boundaries

Unknown locally. DADA-2000 documentation reports accident windows/intervals, but this checkout does not contain the raw annotation files needed to verify the exact `event_start` / `event_end` fields.

## Label Mapping

- Accident category -> `collision`, `near_collision`, or `driving_accident`
- If original category indicates a road user entering the ego path, map to `object_enters_ego_path` only after manual review.
- Driver attention labels are not CASQ event boundaries by themselves.

## Negative / Background Blocks

Background blocks can be sampled outside verified accident windows. If only accident videos are present, negatives should be intra-video pre-event/post-event blocks with careful padding or from verified normal-driving videos if available.

## Known Limitations

- Access may require Baidu Netdisk or Google Drive links from the public repository.
- The compressed dataset is large, so a small approved subset is required first.
- Public split JSON files are not sufficient for CASQ boundary conversion.
- Accident category labels do not directly encode CASQ `object_enters_ego_path` semantics.

## Manual Adjudication Needed

Yes. DADA-2000 can likely support accident and accident-precursor evaluation after access, but local event-boundary files must be inspected first and CASQ event-type mapping needs manual adjudication.

