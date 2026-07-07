# HTS-AQP: Hierarchical Tree Search for Event-Coverage AQP

> Design document, not yet implemented. The direction described here is
> **conceptual**; only the Phase 0 feasibility diagnostic (§3) is actionable
> in the current session. All existing project constraints from `AGENTS.md`
> (no new VLM/GPU/video, no SOTA claim, no safe stopping, no formal
> guarantee, oracle-relative labels only) apply to any future implementation.

---

## 1. Motivation

D1/D2/D3 and the current EventLift-discover-certify all require fixing a
resolution (bin size, chunk size, suppression radius) before search starts.
The same fixed granularity is then applied to every segment — dense 20%
positive-density and sparse 5.8% positive-density segments alike.

**Empirical evidence that this is a problem** (from `PROXY_BIAS_DR_FEASIBILITY.md` and
`EVENTLIFT_RESULTS_SYNTHESIS.md`):

| Segment | Density | Proxy AUC | B7 best recall@0.30 | EventLift best recall@0.30 |
|---:|---:|---:|---:|---:|
| realcartest_0_1570    | 28.0% | 0.78 | 0.152 (macro) | **0.156** (macro) |
| dataset3_0_1200       |  5.8% | 0.31 | 0.056         | **0.000**        |
| dataset3_2400_3462    | 11.2% | 0.56 | 0.074         | **0.222**        |

On dataset3_0_1200 (5.8% density, proxy AUC = 0.31), every existing method
nearly fails because the proxy cannot rank the 7 positives into the top
budget bins. On realcartest_0_1570 (28% density, proxy AUC = 0.78), methods
succeed because a fixed flat scan of ~30% of bins reaches positives.

The core insight behind HTS: **a single oracle call at a coarse time window
can rule out an entire sub-segment in one shot** — something no fixed-
resolution bandit or importance sampler can do, because they must query
individual fine-grained bins before concluding a region is empty.

---

## 2. Design

### 2.1 Multi-resolution time tree

```
整段视频组织成一棵多分辨率时间树 T：
  root: 覆盖整个 segment 的单个区间
  每层往下：每个节点按固定分支因子 b（如 2 或 4）
    切分成 b 个子区间
  leaf 层：粒度对齐现有 atomic bin（10s）

每个节点 v 对应一个时间区间 I_v，维护一个 Beta 后验：
  Beta(alpha_v, beta_v)，表示 "I_v 内还存在未发现事件" 的置信度

初始化（复用已有 prior score）：
  alpha_v = mean_prior_score(I_v) * k0
  beta_v  = (1 - mean_prior_score(I_v)) * k0
  k0 是一个小的伪计数（如 2–5），代表弱先验，
  需在实验中报告 k0 的敏感性
```

**Branching factor b** and **k0** are hyperparameters that replace the
old bin/chunk/suppression-radius set. Branching factor b directly controls
the exploartion-vs-drill tradeoff: smaller b (e.g., 2) drills more
conservatively but builds finer-grained understanding; larger b (e.g., 8)
takes bolder coarse samples but risks over-committing to an uninformative
coarse positive label. **Both b and k0 must be reported and sensitivity-
analyzed, not silently tuned away.**

### 2.2 Unified decision loop (replaces DISCOVER/AUDIT/CERTIFY/SUPPRESS)

The existing EventLift loop used 3–4 separate action types competing in a
utility loop. This design merges them: **every oracle call is a "query
a tree node" operation**, with no separate audit loop.

```text
维护一个 "frontier"（当前可查询的候选节点集合），初始 frontier = {root}

每一步：
  1. 对 frontier 里的每个节点 v，算 UCB 式分数：
     score(v) = alpha_v/(alpha_v+beta_v)
              + c * sqrt(log(t) / (alpha_v+beta_v))
     选 score 最高的 v* 查询 oracle（消耗 1 次 budget，
     和现有所有 baseline 的计 budget 方式完全一致）

  2. Oracle 对 v* 的回答（strict-replay 下，用已有的 dense VLM
     reference labels 做 OR 聚合，不调用新 VLM）：
     coarse_label(I_v) = 已有 atomic bin 标签在 I_v 范围内的 OR

  3a. 如果回答是 negative：
      v* 被剪掉，整个子树不再需要任何后续查询——
      这就是 coarse-to-fine 相对 bandit-at-fixed-resolution 的核心优势：
      一次粗粒度调用就能确认 "这一大片区域大概率没有事件"。
      将剪枝证据添加到 residual coverage report。

  3b. 如果回答是 positive，且 v* 已经是 leaf（对齐 atomic bin）：
      交给 CERTIFY 模块（原样复用）去确认边界，计入 R_core。
      该位置搜索到此结束。

  3c. 如果回答是 positive，但 v* 不是 leaf：
      把 v* 的 b 个子节点加入 frontier（子节点先验可在
      "父节点已知 positive" 信息上做 warm start，
      但哪个具体子节点是 positive 的仍然未知），
      v* 本身移出 frontier。

  4. 重复直到 budget 耗尽。
```

### 2.3 How it addresses previously identified failure modes

| Previous failure (source) | How HTS avoids it |
|---|---|
| AUDIT/repair/discovery compete for budget from separate utility formulae (`RC_AQP_PREFLIGHT.md` Gate 1) | **No separate loops.** One unified decision rule: "which frontier node to query next." The Beta posterior after a negative query on a coarse node *automatically* conveys "this region requires no more budget." |
| D1/D2/D3 granularity hyperparameters that must be pre-set and never suit all segments (`FAILURES.md` D1/D2/D3 vs B7-core) | **Granularity becomes an online decision variable.** The tree drills deeper only in regions where coarse labels are positive. Sparse regions are pruned after a single coarse call; dense regions get finer resolution. |
| Safe stopping statistically unsupportable per-segment (`RC_AQP_PREFLIGHT.md` Gate 2) | **Still not claimed.** The natural residual coverage report from pruned-negative coarse nodes provides per-segment diagnostic evidence, but per the project's prior finding (`p_ucb(15)=0.181`), no high-probability stop certificate is supportable at current segment sizes. HTS makes no new safe-stopping claim. |
| CILS complex sequential model (`AGENTS.md` Never list: only ablation) | HTS's priority score is a simple Beta-UCB, not a sequential model. It is fundamentally simpler, not more complex. |
| SUPG/ABae importance-sampling baselines fail on weak-proxy segments (`EVENTLIFT_RESULTS_SYNTHESIS.md` §7) | Coarse-to-fine does not require bin-level proxy scores to rank positives — a coarse positive/negative label from oracle is independent of the per-bin proxy. If the oracle labels a coarse window negative, that decision does not depend on proxy quality. |

### 2.4 Risks and open assumptions

1. **Coarse-to-fine OR label aggregation simulates a property that may not hold in real deployment.** In strict-replay (this project's current evaluation mode), a coarse oracle call is simulated by OR-ing existing atomic bin labels — this is semantically correct but bypasses the real question: "can a VLM reliably judge whether a 120 s window contains an event at all?" This assumption is **not validated** and must be flagged in any paper as a limitation.

2. **Branching factor b, k0, and exploration constant c are still hyperparameters.** The design converts three old parameters (bin size, chunk size, suppression radius) into three new ones (b, k0, c). The sensitivity of each must be reported. The claim is not "no hyperparameters" but "the best use of coarse resolution is an online decision, not a pre-set beat."

3. **Multi-positive drilling.** When several coarse nodes are positive simultaneously, the tree will create many frontier nodes competing for budget. The UCB priority function must handle this naturally, but the empirical dynamics can only be validated via implementation.

4. **Query cost of a coarse node must equal 1 oracle call.** The design assumes querying a coarse window costs the same as querying an atomic bin. If a future VLM deployment charges per-frame or per-video-time, this breaks. In current strict-replay (one oracle call = one VLM judgment of a 10 s clip), extending the assumption to a 100 s clip is a paper-level assumption that must be explicitly stated as unvalidated.

---

## 3. Phase 0: Offline Coarse-to-Fine Feasibility Diagnostic

Before implementing Beta posteriors, UCB scoring, or frontier management,
Phase 0 runs a single simplified simulation:

> **Using existing atomic-bin reference labels, trace a deterministic
> "God's eye" coarse-to-fine descent that follows the ground-truth coarse
> labels (OR of atomic labels), and count how many oracle calls are needed
> to discover every positive atomic bin in the segment.**

This is a **purely informational** diagnostic: it establishes whether the
coarse-to-fine *basic mechanism* can reduce the number of required oracle
calls relative to a flat exhaustive scan. If this idealized simulation
(which has perfect knowledge of coarse labels) does not substantially
outperform flat scan and existing baselines, then the real algorithm
(which estimates coarse labels from posteriors) will certainly be worse,
and HTS should not be implemented.

See `scripts/hts_aqp_phase0_feasibility.py` and
`outputs/hts_aqp_phase0_feasibility/HTS_PHASE0_FEASIBILITY_REPORT.md`
for the Phase 0 execution and results.

---

## 4. Next phases (conditional on Phase 0 outcome)

Only proceed if Phase 0 concludes "A — strongly feasible" (idealized
coarse-to-fine clearly outperforms flat scan and existing baselines).

| Phase | Scope | Depends on |
|---|---|---|
| Phase 1 | HTS-Discover: build Beta posterior + UCB frontier + tree pruning, no CERTIFY | Phase 0 = A |
| Phase 2 | HTS-DC: integrate existing CERTIFY module for leaf-level boundary expansion | Phase 1 working |
| Phase 3 | HTS full loop: complete unified action loop with residual coverage report | Phase 2 working, strict-replay validation |

---

## 5. Prohibited wording (from AGENTS.md / CLAIMS_LEDGER.md)

- Do NOT claim "HTS is a novel search paradigm" — hierarchical multi-resolution search is standard in time-series, spatial indexing, and game-tree search.
- Do NOT claim "HTS eliminates hyperparameters" — it replaces a set of them with a smaller set (b, k0, c). Sensitivity must be reported.
- Do NOT claim safe stopping or formal guarantee — the project has already concluded this is not supportable (`RC_AQP_PREFLIGHT.md` Gate 2).
- Do NOT claim "VLM coarse label reliability validated" — not yet tested. The strict-replay OR simulation is just that: a simulation.
- Do NOT claim SOTA — HTS has not been implemented or benchmarked. Phase 0 is a feasibility check, not a performance claim.
