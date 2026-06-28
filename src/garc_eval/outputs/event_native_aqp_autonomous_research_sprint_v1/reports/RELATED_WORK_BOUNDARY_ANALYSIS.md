# Related Work Boundary Analysis

---

## 1. Coverage Map

| capability | SUPG | ABae | ARC | ExSample | LAVA | LensWalk | TAD | DriveJudge | STRIVE-D | Hydro | **Ours** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| expensive oracle | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | **✓** |
| budget constraint | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ? | ✓ | **✓** |
| cheap proxy | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | **✓** |
| temporal correlation | ✗ | ✗ | partial | partial | partial | partial | ✓ | ✗ | partial | ✗ | **✓** |
| event boundary | ✗ | ✗ | ✗ | ✓ | ✗ | partial | ✓ | ✗ | ✓ | ✗ | **partial** |
| event clip result | ✗ | ✗ | ✗ | ✗ | ✗ | partial | ✓ | ✗ | ✓ | ✗ | **✓** |
| recall certificate | ✓ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✓ | **✓** |
| audit sampling | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |

**Our unique combination:** expensive oracle + budget + proxy + temporal correlation + event clip + recall certificate + audit. No existing system covers all seven.

---

## 2. Key Differences

### vs SUPG
- **SUPG assumes i.i.d.** — our clips are temporally correlated (P(1→1)=0.325 vs base 0.115, 2.8× clustered)
- **SUPG is frame-level** — we handle clip-level with event stitching
- **SUPG requires proxy AUROC > 0.7** — our proxy has AUROC=0.624, below SUPG's operating range
- **Safe positioning:** "We extend SUPG's AQP framework to non-i.i.d. temporal clips with weak proxies"

### vs ABae
- **ABae estimates class proportion** — we do event clip retrieval
- **ABae is frame-level i.i.d.** — we handle temporal correlation and clip-level results
- **Safe positioning:** "ABae's stratification is for proportion estimation; we adapt it for event clip retrieval with temporal structure"

### vs ARC
- **ARC is frame-level detection** — we are clip-level semantic event
- **ARC doesn't do event stitching** — we merge adjacent positive anchors into event clusters
- **Safe positioning:** "ARC handles frame-level queries; we handle clip-level semantic events that require stitching"

### vs ExSample / LAVA
- **ExSample uses model confidence, not external proxy** — we use handcrafted YOLO proxy
- **LAVA focuses on learned proxy quality** — we focus on budget allocation under weak proxy
- **Both are frame-level** — we are clip-level
- **Safe positioning:** "We focus on budget allocation under weak proxy (AUROC=0.624), not proxy quality improvement"

### vs LensWalk
- **LensWalk is interactive human-in-the-loop** — we are automated with formal budget
- **LensWalk doesn't do recall certificate** — we do
- **Safe positioning:** "We are automated AQP with formal recall guarantee, not interactive exploration"

### vs TAD
- **TAD assumes full oracle scan** — we do budgeted partial scan
- **TAD focuses on boundary localization** — we focus on clip-level recall (boundary is unreliable)
- **TAD doesn't do budget or certificate** — we do
- **Safe positioning:** "TAD requires full oracle scan for boundary localization; we do budgeted clip retrieval with recall certificate"

### vs DriveJudge / DrivingDojo
- **Both are full-scan evaluation/benchmarks** — we are a budgeted AQP method
- **Neither has budget constraint or recall certificate** — we do
- **Safe positioning:** "DriveJudge/DrivingDojo are evaluation frameworks; we are an AQP method that could use them as workload"

### vs STRIVE-D
- **Potential high overlap** — both do driving event retrieval with proxy
- **Need to verify:** does STRIVE-D have budget constraint and recall certificate?
- **Safe positioning:** "If STRIVE-D lacks budget certificate, our contribution is the guarantee layer; if it has it, we differentiate by temporal correlation handling"

### vs Hydro
- **Hydro is relational AQP** — we are video AQP
- **Hydro doesn't handle temporal correlation or clips** — we do
- **Safe positioning:** "We extend AQP from relational to video with temporal structure"

---

## 3. Claims to Avoid

1. **"First AQP system for video"** — ARC, ExSample, LAVA exist
2. **"First proxy-based video query"** — LAVA, ARC use proxies
3. **"First budgeted video query"** — ExSample has adaptive budget
4. **"First driving event retrieval"** — DriveJudge, STRIVE-D exist
5. **"First temporal action detection"** — TAD is a mature field

## 4. Claims That Are Safe

1. **"First AQP system with clip-level recall certificate for temporally correlated semantic events under weak proxy"** — the combination is novel
2. **"Budget decomposition under weak proxy (AUROC < 0.65)"** — SUPG/ABae assume AUROC > 0.7
3. **"Audit-aware budget allocation for proxy-blind positives"** — no existing system does this
4. **"Non-i.i.d. clip-level statistical guarantee"** — SUPG is i.i.d., we handle temporal correlation
5. **"Proxy-agnostic feasibility analysis"** — connecting proxy AUROC to minimum budget for γ-recall

---

## 5. DB Conference Positioning

For VLDB/SIGMOD/ICDE, the positioning should be:

**"Approximate Query Processing for Semantic Event Clip Retrieval over Long Videos with Expensive Oracles"**

- Emphasize the **AQP/query-processing** framing, not the driving/video perception framing
- The driving workload is the **representative scenario**, not the contribution
- The contribution is the **budget allocation + guarantee** machinery
- Position alongside SUPG/Hydro as "AQP with expensive predicates" extended to video
- The temporal correlation and clip-level structure are the **novel AQP challenges** vs SUPG's i.i.d. frames
