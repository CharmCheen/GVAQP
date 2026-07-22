# AGENT START HERE — 60 秒上下文

## 当前方法

```text
MAP-anchor-only → BB-EM/K3 → EventRelation
```

K3：gap limit + duration prior + queried-negative hard barrier。

## 当前可信结论

- materialization gap：pilot confirmed；
- K3 minimal operator：pilot confirmed，待 trigger/path audit；
- MAP anchor probing：pilot supported；
- native ARC 在 B≤10 raw overlap_any F1 更强；
- full SEHS、actor graph、VOI、certificate：未成立。

## 任何 agent 的第一规则

不要把 target design 当成已实现结果；不要访问未查询 label；不要用 reference 调 query；不要在 test 调参。

## 当前执行顺序

```text
repo sync
→ preflight audits
→ human GT / canonical anchor
→ candidate + planner + materializer ceilings
→ Minimal SEHS-node
→ independent audit prototype
→ frozen cross-video
→ full actor graph / VOI only if gates pass
```

## 最关键 GO/NO-GO

- candidate ceiling <0.80：停止 planner；
- oracle planner ceiling 低：扩 action space；
- Minimal SEHS 不超过 ARC+BB-EM：保留 BB-EM-only；
- audit coverage 失败：不得称 certificate；
- cross-video 不稳定：缩小 claim。

详细规范见 `README.md` 和编号文档。
