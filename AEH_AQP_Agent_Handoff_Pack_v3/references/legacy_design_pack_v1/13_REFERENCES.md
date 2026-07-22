# 13 — Primary References and Relevance Map

以下优先列一手论文/官方版本。文献 agent 应核对最终 BibTeX。

## AQP / expensive predicates

1. Daniel Kang et al. **Approximate Selection with Guarantees using Proxies.** PVLDB 13(11), 2020. DOI: `10.14778/3407790.3407807`.  
   关联：record-level selection、oracle budget、precision/recall guarantee；本课题需区别 event object 与 residual completeness。

2. Daniel Kang et al. **Accelerating Approximate Aggregation Queries with Expensive Predicates.** PVLDB 14(11), 2021. DOI: `10.14778/3476249.3476280`.  
   关联：ABae proxy stratification 与 allocation；本课题不是 aggregate estimator。

3. Daniel Golovin and Andreas Krause. **Adaptive Submodularity: A New Approach to Active Learning and Stochastic Optimization.** COLT 2010 / later journal treatment.  
   关联：restricted distinct-event coverage objective 的可能 greedy guarantee；完整 boundary utility 未必满足。

## Video query processing

4. Yue Chen et al. **ARC: Approximate Relevant Clip Query in Large-Scale Video Repositories.** SIGIR 2025. DOI: `10.1145/3726302.3729896`.  
   关联：最接近 relevant-clip baseline；差异需落在 event semantics、dedup、actor/relations、audit。

5. Jaeho Bang et al. **Seiden: Revisiting Query Processing in Video Database Systems.** PVLDB 16(9), 2023. DOI: `10.14778/3598581.3598599`.  
   关联：exploration–exploitation、temporal continuity、MAB reward；本课题 reward 是 EventRelation gain。

6. Enhao Zhang et al. **EQUI-VOCAL: Synthesizing Queries for Compositional Video Events from Limited User Interactions.** PVLDB 16(11), 2023. DOI: `10.14778/3611479.3611482`.  
   关联：spatio-temporal scene graph、active query synthesis；说明“使用 graph”本身不足以构成 novelty。

7. Wenjia He and Michael J. Cafarella. **Controlled Intentional Degradation in Analytical Video Systems / related selection-limit work.**  
   关联：稀疏索引与 query-time patching 的系统思路；需按最终引用核对具体版本。

## Semantic operators / AI query systems

8. Liana Patel et al. **Semantic Operators and Their Optimization: Enabling LLM-Based Data Processing with Accuracy Guarantees in LOTUS.** PVLDB 18, 2025. DOI: `10.14778/3749646.3749685`.  
   关联：明确 semantic operator reference behavior、cost/accuracy optimization；启发 EVENT_SELECT/BB-EM 的正式语义。

## Driving / safety video

9. Chonghao Sima et al. **DriveLM: Driving with Graph Visual Question Answering.** ECCV 2024.  
   关联：驾驶中 object→interaction→planning 的 graph-structured reasoning；不是 budgeted query algorithm。

10. Daniel C. Moura, Shizhan Zhu, Orly Zvitia. **Nexar Dashcam Collision Prediction Dataset and Challenge.** CVPR 2025 Workshop on Autonomous Driving. arXiv:`2503.03848`.  
    关联：真实 dashcam collision/near-collision、event moment 与 alert time；可作为外部数据源。

11. Rui Gan et al. **CrashSight: A Phase-Aware, Infrastructure-Centric Video Benchmark for Traffic Crash Scene Understanding and Reasoning.** CVPR 2026 Workshop / arXiv:`2604.08457`.  
    关联：phase-aware crash understanding；主要是 roadside，不可替代 ego-centric validation。

## Sampling / residual estimation

12. D. G. Horvitz and D. J. Thompson. **A Generalization of Sampling Without Replacement from a Finite Universe.** JASA, 1952.  
    关联：known-inclusion-probability population total estimator；本课题需 canonical anchor 唯一计数。

13. I. J. Good. **The Population Frequencies of Species and the Estimation of Population Parameters.** Biometrika, 1953.  
    关联：unseen-mass 思路；只能作为探索，不能未经假设验证直接生成 event certificate。

## 阅读顺序

1. ARC / SUPG / ABae：确定 baseline query object 与 guarantee；
2. EQUI-VOCAL / Seiden：确定 graph 与 adaptive video querying 的已有边界；
3. LOTUS：学习 operator semantics 与 optimization 写法；
4. DriveLM / Nexar：定义 driving event schema；
5. Adaptive submodularity / HT：评估理论与 audit feasibility。
