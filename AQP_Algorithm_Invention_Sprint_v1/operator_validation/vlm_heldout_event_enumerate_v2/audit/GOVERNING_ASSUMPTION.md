# Governing assumption

`ORACLE_EXACT_BY_USER_ASSUMPTION = true`  
`REFERENCE_TYPE = VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`  
`HUMAN_GT = false`  
`REAL_WORLD_SEMANTIC_CLAIM = false`

The user authorizes existing VLM oracle outputs as exact for this AQP
abstraction only. Direct artifacts still must establish that an observation
belongs to `test.mov`; exactness does not license transferring annotations
from different content or treating YOLO vehicle counts as VEPC labels.
