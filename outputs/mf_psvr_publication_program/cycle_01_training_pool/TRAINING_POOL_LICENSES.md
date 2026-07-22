# MF-PSVR Cycle 1 training-pool licenses

Status: **Nexar eligible; DrivingDojo-mini quarantined**.

## Nexar Collision Prediction

- Exact source: <https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction>
- Audited repository revision: `aa97deda5a59f00bb7187739053b7c72e14374df`
- Revision-addressed official license: <https://huggingface.co/datasets/nexar-ai/nexar_collision_prediction/raw/aa97deda5a59f00bb7187739053b7c72e14374df/LICENSE>
- License name in the official dataset card: `nexar-open-data-license`
- Raw license SHA-256 at audit: `9c62949a76b4a3039023a93a31aac964847cbcfcac8376daaa541cc620788824`

The exact retrieved license and revision-API bytes are preserved under `provenance/` with URL,
retrieval time, and content-hash receipts.

The license grants use, copying, modification, and distribution subject to attribution,
retention of terms on redistribution, no resale without consent, ethical-use restrictions,
legal compliance, and an as-is disclaimer. This research use is in scope. The project must cite
Nexar and Moura et al.; must not redistribute the videos without retaining the terms; and must not
attempt re-identification, surveillance, weaponization, deceptive media, unsafe-system development,
or exploitative use. This is a custom license, not MIT/Apache.

Primary provenance is also supported by the CVPR 2025 workshop paper:
<https://openaccess.thecvf.com/content/CVPR2025W/WAD/papers/Moura_Nexar_Dashcam_Collision_Prediction_Dataset_and_Challenge_CVPRW_2025_paper.pdf>.

## DrivingDojo-mini

- Exact source: <https://huggingface.co/datasets/jiaweihe/DrivingDojo-mini>
- Audited repository revision: `97092ae989332696f88567f8dfaae704b1529b59`
- Official project page linking the mini archive: <https://drivingdojo.github.io/>
- Full dataset repository: <https://huggingface.co/datasets/Yuqi1997/DrivingDojo>

Observed evidence: the exact mini repository contains only `.gitattributes` and
`drivingdojo_mini.zip`; its API has no license tag and the archive contains no LICENSE, COPYING,
NOTICE, or README. The later full-dataset repository is marked Apache-2.0, but that does not directly
establish terms for the independently hosted mini archive. The project website's CC BY-SA notice
explicitly concerns the website source, not the dataset bytes.

Decision: all 32 mini sessions are quarantined. They may not be used for detector extraction,
oracle labeling, training, evaluation, or publication claims until a direct license grant covering
the exact mini archive is documented. This conservative decision can be revised by direct evidence;
it is not a claim that reuse is forbidden.
