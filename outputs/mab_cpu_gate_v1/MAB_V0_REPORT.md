# MAB-v0 report

## budget 5
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.0424 |      0.0424 | 0.0471 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0      |      0      | 0.0222 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.0545 |      0.0545 | 0.0364 |

## budget 10
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.0783 |      0.0783 | 0.0826 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0.0327 |      0.0327 | 0.0462 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.0576 |      0.0576 | 0.0593 |

## budget 20
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.1047 |      0.1048 | 0.1163 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0.0961 |      0.0961 | 0.0964 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.0996 |      0.0996 | 0.1028 |

## budget 50
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.1539 |      0.1468 | 0.1947 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0.2192 |      0.2192 | 0.2155 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.2237 |      0.2237 | 0.2137 |

## budget 80
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.226  |      0.2152 | 0.2591 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0.3055 |      0.3055 | 0.3046 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.2911 |      0.2911 | 0.2775 |

## budget 100
| cluster                                     |   relation_greedy |   top_proxy |     ts |
|:--------------------------------------------|------------------:|------------:|-------:|
| DALI_Q_VULNERABLE_ROAD_USER_CONFLICT_V1     |            0.2677 |      0.2564 | 0.2837 |
| HANGZHOU_Q_VULNERABLE_ROAD_USER_CONFLICT_V1 |            0.3477 |      0.3477 | 0.3476 |
| WUHAN_Q_VULNERABLE_ROAD_USER_CONFLICT_V1    |            0.3403 |      0.3403 | 0.3249 |

## gates and scope
- Scope: FIXED_CANDIDATE_REPLAY only; no endogenous acquisition claim.
- Model: Bayesian logistic (Laplace) contextual TS over visible_* features, top-50 proxy candidates.
- Routes at entry (corrected): {"action_space": "ACTION_SPACE_GO", "context": "INCONCLUSIVE_CONTEXT", "lookahead": "MYOPIC_CONTEXTUAL_MAB_IS_ADEQUATE"} {'action_space': 'ACTION_SPACE_GO', 'context': 'CONTEXTUAL_MODEL_VIABLE', 'lookahead': 'MYOPIC_CONTEXTUAL_MAB_IS_ADEQUATE'}