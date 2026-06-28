# SMOKE_TEST_REPORT.md - realcartest YOLOv8n 60s smoke

| Key | Value |
|---|---:|
| processed_frame_count | 120 |
| actual_sampling_fps | 2.0 |
| wall_clock_time_sec_this_invocation | 14.788 |
| effective_processed_fps_this_invocation | 8.115 |
| detections_per_frame_mean | 9.608 |
| detections_per_frame_median | 10.000 |
| detections_per_frame_max | 23 |
| vehicle_like_detections | 955 |
| person_detections | 173 |
| error_frame_count | 0 |
| estimated_full_video_runtime_sec | 982.8 |
| estimated_full_video_runtime_min | 16.38 |
| estimated_output_file_size_bytes | 27483511 |
| gpu_cpu_usage | NVIDIA A800-SXM4-80GB, 81920 MiB, 80593 MiB |
| fields_complete | YES |

## Class Distribution

| class_name | count |
|---|---:|
| car | 879 |
| person | 173 |
| truck | 66 |
| umbrella | 10 |
| potted plant | 4 |
| bicycle | 4 |
| motorcycle | 3 |
| bus | 3 |
| dog | 3 |
| fire hydrant | 2 |
| refrigerator | 2 |
| skateboard | 1 |
| bench | 1 |
| stop sign | 1 |
| tv | 1 |

## Smoke Decision

`SMOKE_PASS_CONTINUE_FULL_RUN`

Reasons:
- YOLO ran, frames processed, fields complete, full run is resumable
