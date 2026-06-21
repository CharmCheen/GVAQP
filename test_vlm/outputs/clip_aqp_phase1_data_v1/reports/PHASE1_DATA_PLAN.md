# Phase 1 Data Plan: CASQ Event-Boundary Ingestion

## Scope

Phase 1-data prepares clean event-boundary ingestion for CASQ/G-ClipAQP. It does not download large datasets, run VLMs, train models, build a perception stack, fabricate event boundaries, or treat pseudo-events as human truth.

Prior evidence:

- Phase 0 repair remains underpowered because the current benchmark has only 29 pseudo-events.
- Phase 0.6 recommends expanding to at least 200 clean events, with 500 as the preferred target.
- Existing pseudo-events can be reused only for debugging ingestion and schema validation, not as clean evaluation truth.

## Dataset Ranking

| rank | dataset | best use | event-boundary evidence | 200 events | 500 events | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Nexar Collision Prediction | first small subset for accident-precursor CASQ | public dataset card and paper document `time_of_event` and `time_of_alert` for positive collision/near-miss cases | likely | likely | best first controlled subset |
| 2 | DoTA | larger temporal-boundary anomaly ingestion | official README documents `anomaly_start` and `anomaly_end` in metadata | likely | likely | best large clean-boundary candidate after subset audit |
| 3 | DADA-2000 / LOTVS-DADA | accident-window backup | public source reports accident windows/intervals, but local split files do not expose boundaries | likely after access | likely after access | useful but access/schema uncertainty is higher |
| 4 | Micro-CASQ-v0 | manual clean smoke set | local template only | no without large manual effort | no without large manual effort | fallback sanity set |

## Best Dataset For Clean Event-Boundary CASQ Evaluation

Nexar is the recommended first dataset because it directly supports a CASQ query of `collision_or_near_collision_precursor` using the documented interval from `time_of_alert` to `time_of_event`, has normal-driving negatives, and has enough positives in the public training set to target 200 / 500 events if access is approved.

DoTA is the strongest larger temporal-boundary benchmark candidate because the official metadata has anomaly start/end fields and the dataset is larger. It is second for the first ingestion step because the boundary units appear to be frame indices and the CASQ query mapping from anomaly class to ego-path relevance needs more adjudication.

## Event Boundary Availability

| dataset | event_start/event_end or equivalent | local raw metadata present | conversion status |
| --- | --- | --- | --- |
| DoTA | documented `anomaly_start` / `anomaly_end` frame-index boundaries | no | scaffolded; requires approved metadata subset and explicit verified fps |
| DADA-2000 | reported accident intervals/windows, but not verified in local files | no | scaffolded; requires approved interval annotation files |
| Nexar | documented `time_of_alert` / `time_of_event` for positive cases | no | scaffolded; maps only precursor interval, not fabricated collision duration |
| Micro-CASQ-v0 | none yet; manual template requires boundaries | template only | ready for manual annotation |

## CASQ Query Support

| query | Nexar | DoTA | DADA-2000 | Micro-CASQ-v0 |
| --- | --- | --- | --- | --- |
| collision / near-collision precursor | strong | medium | strong after interval access | strong if manually annotated |
| object-enters-ego-path | weak-to-medium; needs adjudication | medium; needs class/object review | medium; needs category/object review | strong if annotation policy targets it |
| accident precursor | strong | medium | strong | strong if manually annotated |

## Access, Download, And License Steps

- Nexar: review Hugging Face/Kaggle dataset terms, confirm open-license restrictions, then download only a small approved subset of metadata and videos. Do not fetch the full 31.4 GB release without explicit approval.
- DoTA: review upstream GitHub MIT code license and data-link terms, then fetch metadata and a small number of clips first. Do not download the full 55 GB release without explicit approval.
- DADA-2000: confirm access to Baidu Netdisk or Google Drive release links and inspect interval annotation files before any conversion. Do not download the 53 GB or 116 GB releases without explicit approval.
- Micro-CASQ-v0: choose source clips with documented provenance and license, then manually annotate boundaries in the local template.

## Smallest Subset To Ingest First

Recommended first subset:

- Dataset: Nexar
- Query: `collision_or_near_collision_precursor`
- Positives: 25 collision/near-collision videos with `time_of_alert` and `time_of_event`
- Negatives: 25 normal-driving videos
- Unit size: 10 seconds for initial blocks, with ambiguous boundary padding excluded from negatives
- Purpose: verify local metadata schema, video path handling, unit generation, boundary overlap logic, and report generation

If Nexar access is blocked, use DoTA metadata plus 25 anomaly clips and 25 background intervals as the first fallback. If both are blocked, use Micro-CASQ-v0 for a small manually annotated smoke set.

## Limitations And Uncertainty

- No external raw videos or annotation files are present locally yet.
- Dataset-level event labels are not human-adjudicated CASQ truth until the query mapping is reviewed.
- Nexar supports an accident-precursor interval; it does not by itself define the full semantic interval of every collision.
- DoTA frame-index boundaries need verified fps before second-based CASQ conversion.
- DADA-2000 interval schemas remain unknown until the actual annotation files are acquired.

