# G-ARC 真实视频实验 Session 完整记录

## 一、目标

为 G-ARC 实验建立真实视频的 proxy/oracle 数据管线，验证 proxy/oracle gap，测试现有基线方法（SUPG、ABAE），并实现第一个 G-ARC recall certificate MVP。

**不做：** ARC 复现、G-ARC 完整实现、人类标注、新数据集下载。

---

## 二、环境

| 项目 | 值 |
|------|-----|
| Python | 3.10.20 (conda env: garc) |
| ultralytics | 8.4.51 |
| PyTorch | 2.12.0+cu126 |
| GPU | NVIDIA RTX 2080 Ti |
| Proxy 模型 | YOLOv8n (6.3MB, ~37 mAP, 93.9 fps) |
| Oracle 模型 | YOLOv8x (131MB, ~54 mAP, 44.9 fps) |
| SUPG 源码 | `/qiuyeqing/llama_prl/G-ARC/refe_repos/supg` (editable install) |
| G-ARC 管线 | `/qiuyeqing/llama_prl/G-ARC/garc_eval` |
| 工作目录 | `/qiuyeqing/llama_prl/G-ARC/try_or_no` |

---

## 三、视频数据

| 项目 | test.mov | realcartest_5k.mp4 |
|------|----------|---------------------|
| 来源 | 原始测试视频 | 从 realcartest.mp4 (66.5min, 795MB) 截取前 5000 帧 |
| 分辨率 | 2940×1912 | 1920×1080 |
| FPS | 41.24 | 24.00 |
| 帧数 | 1,775 | 5,000 |
| 时长 | 43s | 208s (3.5min) |
| 特征 | 连续车流 | 两极分化（73% 空帧 + 27% 有车帧） |

---

## 四、实验总览

### 实验 0: 真实视频 CSV 生成

**输入：** 视频文件 + YOLOv8n + YOLOv8x
**脚本：** `video_to_supg_csv.py`
**输出：** `video_supg.csv` (test.mov, 1775×29), `realcar_5k.csv` (realcar_5k, 5000×29)

**CSV 列：** frame_idx, processed_idx, timestamp_sec, proxy_vehicle_count, oracle_vehicle_count, proxy_score (= count + 0.01×conf_sum), oracle_score, proxy_positive_K{K}, oracle_positive_K{K}, label_K{K}, id, proxy_score_supg

**两个视频的 proxy/oracle 对比：**

| 指标 | test.mov K=5 | realcar_5k K=5 | realcar_5k K=10 |
|------|:---:|:---:|:---:|
| 正样本率 | 34.65% | 73.84% | 37.36% |
| Proxy precision vs oracle | 90.5% | — | — |
| Proxy recall vs oracle | 32.4% | — | — |
| F1 | 0.477 | 0.888 | 0.600 |

**结论：** Proxy 有信号但漏检严重。realcar_5k 的 proxy/oracle 一致性好于 test.mov。

---

### 实验 1: Runtime Cost Benchmark

**输入：** video_supg.csv + YOLO 模型
**脚本：** `runtime_cost_benchmark.py`
**输出：** `runtime_cost_benchmark_report.md`

**测量 (100帧, RTX 2080 Ti)：**

| 组件 | FPS |
|------|-----|
| Proxy-only (YOLOv8n) | 93.9 |
| Oracle-only (YOLOv8x) | 44.9 |
| Dual sequential | 31.0 |
| CSV read + stitch | 21ms |

**预估加速比 (N=1775, precomputed proxy table)：**

| oracle_ratio | 加速比 |
|:---:|:---:|
| 5% | 20× |
| 10% | 10× |
| 20% | 5× |

**结论：** 如果 proxy 表离线预计算好，query-time 可以从 39.5s 降到 2–8s。

---

### 实验 2: SUPG Query Benchmark (原版 SUPG 框架)

**输入：** `video_supg_k5.csv` (SUPG 格式: id, label, proxy_score)
**脚本：** `supg_query_benchmark.py`（调用 `refe_repos/supg` 原版代码）
**输出：** `supg_query_benchmark_report.md`

**5 种 selector 测试：**

| Budget | Selector | 选出帧数 | 加速比 | Precision |
|:---:|------|:---:|:---:|:---:|
| 5% | PrecisionSelector (importance) | 49 | **36.4×** | 99.2% |
| 10% | PrecisionSelector (importance) | 220 | **8.1×** | 88.2% |
| 20% | PrecisionSelector (importance) | 584 | **3.0×** | 72.0% |
| 5% | RecallSelector (sqrt) | 1775 | 1.0× | 34.7% |
| 5% | NaiveRecallSelector | 1233 | 1.4× | 45.4% |

**结论：** SUPG PrecisionSelector 用 5% 预算达到 36× 加速和 99% 精度。RecallSelector 选了几乎全部帧，无加速。

---

### 实验 3: G-ARC Experiment 1 — 多方法对比 (test.mov K=5)

**输入：** `video_supg_k5.csv`
**脚本：** `garc_eval.experiments.run_supg_real_frames`（现有 G-ARC 管线）
**输出：** `garc_experiment1/` (6 组配置 × summary.csv + boxplots)

**方法：** U-NOCI-RT, U-CI-RT, SUPG-RT, U-NOCI-PT, SUPG-PT
**参数：** budget={100,200,400}, gamma={0.8,0.9}, trials=50

**SUPG-PT 结果：**

| Budget | 选出帧数 | Precision | Recall | 加速比 |
|:---:|:---:|:---:|:---:|:---:|
| 100 | 46 | **100%** | 7.5% | 39× |
| 200 | 88 | **100%** | 14.3% | 20× |
| 400 | 163 | **100%** | 26.5% | 11× |

**其他方法：**
- U-NOCI: 12–50% failure rate，不稳定
- U-CI-RT / SUPG-RT: 选了几乎全部帧，0% failure 但无加速

**结论：** SUPG-PT 精度封顶但召回低（7–27%）。U-NOCI 不可靠。

---

### 实验 4: G-ARC Experiment 2 — K 阈值敏感性 (test.mov)

**输入：** `video_supg_k3.csv`, `video_supg_k5.csv`, `video_supg_k7.csv`
**脚本：** `garc_eval.experiments.run_supg_real_frames`
**输出：** `garc_experiment2/` (k3, k7 各 6 组配置)

**K=3 (76.23% 正样本, 密集)：**
- SUPG-PT budget=400: 选出 805 帧, precision 98%, recall 58%
- 部分 seed 下 SUPG 崩溃（源码 bug，高正样本率触发）

**K=5 (34.65%, 中等)：** 同实验 3

**K=7 (9.41%, 稀疏)：**
- SUPG-PT budget=100: 选出 12 帧, **100% precision**, 7.6% recall, **132× 加速**
- SUPG-PT budget=400: 选出 40 帧, **100% precision**, 24.2% recall, **44× 加速**
- U-NOCI-PT budget=100: **54% failure rate**

**结论：** 正样本越稀疏，SUPG 越有用。K=7 时用 <1% oracle 预算达到 100% 精度。

---

### 实验 5: SUPG (realcar_5k K=10)

**输入：** `realcar_k10.csv`
**脚本：** `garc_eval.experiments.run_supg_real_frames`
**输出：** `realcar_exp/k10/`

| Budget | Method | Failure Rate | Precision | Recall | Selected |
|:---:|--------|:---:|:---:|:---:|:---:|
| 200 | SUPG-PT | **0%** | **100%** | 5.9% | 106 |
| 200 | U-NOCI-PT | **57%** | 80.7% | 52.1% | 1233 |
| 500 | SUPG-PT | **0%** | **100%** | 14.2% | 258 |
| 500 | U-NOCI-PT | **30%** | 82.7% | 52.6% | 1202 |

**结论：** 与 test.mov K=5 模式一致。SUPG-PT 100% precision，低 recall，0% failure。

---

### 实验 6: ABAE + Clip Benchmark

**输入：** `abae_k5_input.csv` (test.mov), `abae_realcar_k5.csv` (realcar_5k)
**脚本：** `abae_clip_benchmark.py`
**输出：** `abae_clip_results/`

#### test.mov (K=5, 34.65% 正样本率, budget=500, 30 trials)

**聚合：**

| Method | AVG 误差 | AVG CI 宽度 | AVG 覆盖率 | COUNT CI 宽度 |
|--------|:---:|:---:|:---:|:---:|
| Uniform | 1.1% | 0.336 | 93.3% | 150.2 |
| ABAE-paper | **0.9%** | **0.284** | **100%** | **118.4** |

**Clip (15 个真实 clip, min_len=3, gap=3)：**

| Method | Clip Recall | mIoU |
|--------|:---:|:---:|
| Uniform | 16.2% | 0.143 |
| ABAE-paper | 15.8% | 0.144 |

#### realcar_5k (K=5, 73.84% 正样本率, budget=500, 30 trials)

**聚合：**

| Method | AVG 误差 | AVG CI 宽度 | AVG 覆盖率 | COUNT CI 宽度 |
|--------|:---:|:---:|:---:|:---:|
| Uniform | 1.4% | 0.618 | 86.7% | 379.9 |
| ABAE-paper | **0.8%** | **0.528** | **93.3%** | **292.4** |

**Clip (24 个真实 clip, min_len=5, gap=3)：**

| Method | Clip Recall | mIoU |
|--------|:---:|:---:|
| Uniform | 2.2% | 0.026 |
| ABAE-paper | 1.8% | 0.025 |

**结论：** ABAE 聚合好（CI 窄 15–21%），但 clip recall 极差（2–16%）。

---

### 实验 7: G-ARC Certificate MVP

**输入：** `realcar_5k.csv`
**脚本：** `garc_certificate_mvp.py`
**输出：** `garc_certificate_mvp/garc_certificate_mvp_results.csv`, `summary.csv`, `garc_certificate_mvp_report.md`

**方法：**
1. 用 proxy_vehicle_count >= K 阈值生成 candidate clips
2. Non-candidate 区域均匀采样 s 帧
3. Hoeffding 上界估计 NC 区域正样本率
4. 转换为漏掉 clip 上界 M_U
5. 计算 recall 下界 recall_LB = H / (H + M_U)

**参数：** K=10, tau={5,10,20}, s={100,200,500,1000}, gamma={0.8,0.9}, delta=0.05, seeds=50

**结果（所有配置）：**

| tau | s | actual_recall | cert_recall_LB | pass_rate | H | M_U |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 5 | 100 | 0.025 | 0.003 | **0%** | 1 | 299 |
| 10 | 500 | 0.130 | 0.028 | **0%** | 3 | 105 |
| 20 | 1000 | 0.182 | 0.042 | **0%** | 2 | 45 |

**没有任何配置通过证书（gamma=0.8 或 0.9）。**

**原因分析：**
- Candidate generation 太弱：proxy 只找到 1–3 个 true clip（H=1–3），actual_recall 只有 2.5%–18.2%
- NC region 太大：3623–3961 帧（72–79%）在候选区域之外
- Hoeffding 上界 q_U ≈ 0.25–0.38，意味着 NC 区域可能有 25–38% 是正样本
- Frame-to-clip 转换太松：floor(F_U / tau) 假设最坏情况

**结论：** 瓶颈在 candidate generation，不在审计框架。需要先提升 proxy 候选质量。

---

## 五、综合发现

### 方法对比总结

| 方法 | 擅长 | 不擅长 |
|------|------|--------|
| SUPG-PT | Frame selection, 100% precision | 低 recall (5–27%) |
| ABAE | Aggregation (CI 窄 15–21%) | Clip 发现 (recall 2–16%) |
| U-NOCI | — | 12–57% failure rate |
| G-ARC Certificate MVP | 有效的 recall 下界 | 过于保守（bound gap 大） |

### Proxy/oracle gap 已验证

- test.mov: F1=0.477 (K=5), proxy 漏检严重
- realcar_5k: F1=0.888 (K=5), proxy 一致性好但 clip 仍失败

### Clip 问题在两个视频上都存在

- test.mov: ABAE clip recall 16%
- realcar_5k: ABAE clip recall 2%（更差，因为正样本更密，采样更难覆盖）

### 三个结论验证了 ARC 的重要性

1. **Proxy 信号有价值**（F1=0.888）但帧级方法没充分利用
2. **帧级方法（SUPG/ABAE）解决不了 clip 问题**（recall 2–16%）
3. **Temporal continuity 是被浪费的信息** — ARC 的 candidate clip generation 正是利用这个结构

---

## 六、ARC/G-ARC 概念框架

### ARC

针对 relevant clip query，用 proxy 剪枝 + 候选 clip 生成 + oracle 精化。置信度是 candidate-side (precision-like)，不审计漏掉的 clip。

### G-ARC 目标

在 ARC 基础上加 recall 认证层：

```
Pr[ClipRecall(C_hat, C_star; theta, tau) >= gamma] >= 1 - delta
```

### G-ARC 流程

1. ARC-style 候选生成 (proxy scores)
2. 候选验证 (oracle calls)
3. 边界验证
4. 非候选区域审计 (verification sampling)
5. 漏掉 clip 上界估计
6. Recall 下界 / 证书

---

## 七、所有输出文件

```
outputs/garc_meeting_pack/
├── real_video_csv_pipeline/
│   ├── yolo_environment_audit.md          # 环境审计
│   ├── video_to_supg_csv.py              # CSV 生成脚本
│   ├── video_supg.csv                     # test.mov (1775×29)
│   ├── realcar_5k.csv                     # realcar_5k (5000×29)
│   ├── video_supg_report.md               # 含 Conceptual Framing
│   ├── video_supg_k5.csv / k3.csv / k7.csv
│   ├── realcar_k10.csv
│   ├── abae_k5_input.csv / abae_realcar_k5.csv
│   ├── runtime_cost_benchmark.py
│   ├── runtime_cost_benchmark_report.md
│   ├── supg_query_benchmark.py
│   ├── supg_query_benchmark_report.md
│   ├── abae_clip_benchmark.py
│   ├── README.md                          # 含 ARC/G-ARC 关系
│   ├── arc_garc_concept_note.md
│   ├── garc_experiment1/                  # test.mov 多方法对比
│   ├── garc_experiment2/                  # test.mov K 阈值敏感性
│   ├── realcar_exp/                       # realcar_5k SUPG 实验
│   └── abae_clip_results/                 # ABAE clip 结果
├── garc_certificate_mvp/
│   ├── garc_certificate_mvp.py            # Certificate MVP 脚本
│   ├── garc_certificate_mvp_results.csv   # 每 trial 结果
│   ├── summary.csv                        # 汇总
│   └── garc_certificate_mvp_report.md     # 报告
└── session_log.md                         # 本文件
```

---

## 八、关键数字速查

| 指标 | test.mov | realcar_5k |
|------|----------|------------|
| 帧数 | 1,775 | 5,000 |
| K=5 正样本率 | 34.65% | 73.84% |
| K=10 正样本率 | 0.51% | 37.36% |
| Proxy/oracle F1 (K=5) | 0.477 | 0.888 |
| SUPG-PT precision | 100% | 100% |
| SUPG-PT recall (budget=500) | 26.5% (K=5) | 14.2% (K=10) |
| ABAE CI 窄于 Uniform | 15% | 15% |
| ABAE clip recall | 16% | 2% |
| Certificate MVP pass rate | — | 0% |
| Oracle fps | 44.9 | 44.9 |
| Proxy fps | 93.9 | 93.9 |

---

## 九、下一步

| 优先级 | 事项 | 原因 |
|:---:|------|------|
| 1 | 改进 candidate generation（降低 proxy 阈值 / SUPG-PT） | 当前 MVP 瓶颈，不需要 ARC 源码 |
| 2 | 拿 ARC 源码做 baseline 对比 | 论文需要 |
| 3 | Run-aware window audit | 改进审计框架，避免 frame-to-clip 松转换 |
| 4 | 用 ARC candidate generator 替换 | 提升 H，让 certificate 通过 |
