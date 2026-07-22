#!/usr/bin/env python3
"""Build the result-blind PSVR/Rollout-PSVR D1--D4 freeze package.

This script is static-only: it reads text/config/profile artifacts, writes the
freeze package, and never imports or invokes a simulator, model, media reader,
GPU runtime, oracle, or held-out dataset.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/psvr_rollout_preimplementation"
OUT = ROOT / "outputs/psvr_rollout_preimplementation"
SOURCE = {
    "contract": ROOT / "docs/PSVR_RESEARCH_CONTRACT.md",
    "autonomous_contract": ROOT / "docs/PSVR_AUTONOMOUS_RESEARCH_CONTRACT.md",
    "hypotheses": ROOT / "docs/PSVR_HYPOTHESIS_REGISTRY.md",
    "decisions": ROOT / "docs/PSVR_DECISION_LEDGER.md",
    "failures": ROOT / "docs/PSVR_FAILURE_CATALOG.md",
    "two_video_report": ROOT / "outputs/psvr_two_video_loop/FINAL_REPORT.md",
    "stage_a_report": ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a/STAGE_A_TO_MODEL_FINAL_REPORT.md",
    "deadline_decision": ROOT / "outputs/psvr_autonomous_research/stage_1_deadline_safety/h_ds1_tail_guard_v2_persistent_k3/DECISION.json",
    "action_profile": ROOT / "outputs/psvr_autonomous_research/stage_1_deadline_safety/h_ds1_tail_guard_v2_persistent_k3/action_profile.json",
    "commit_profile": ROOT / "outputs/psvr_autonomous_research/stage_1_deadline_safety/h_ds1_tail_guard_v2_persistent_k3/commit_profile.json",
    "unit_manifest": ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/unit_table.csv",
    "scan_runtime": ROOT / "scripts/run_psvr_two_video_physical.py",
    "proxy_cost": ROOT / "outputs/psvr_two_video_loop/proxy_finalization/physical_cost/Y8_PHYSICAL_COST.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def splitmix64_sequence(seed: int, n: int) -> list[int]:
    mask = (1 << 64) - 1
    state = seed & mask
    result = []
    for _ in range(n):
        state = (state + 0x9E3779B97F4A7C15) & mask
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
        result.append((z ^ (z >> 31)) & mask)
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, path in SOURCE.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing authoritative input {name}: {path}")
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    action = json.loads(SOURCE["action_profile"].read_text())
    commit = json.loads(SOURCE["commit_profile"].read_text())
    action_upper = action["tail_bound"]["upper_seconds"]
    commit_upper = commit["tail_bound"]["upper_seconds"]
    confirm_upper = action_upper + commit_upper
    proxy = json.loads(SOURCE["proxy_cost"].read_text())
    legacy_scan_formula = max(2.0, 1.5 * proxy["p95_latency_ms"] / 1000 * 50 + 1.0)
    source_hashes = {name: sha(path) for name, path in SOURCE.items()}

    utility = {
        "registry_id": "PSVR_UTILITY_REGISTRY_V1",
        "status": "FROZEN",
        "initial_utility": {"committed_set": [], "u0": 0},
        "primary_surrogate": "sum_TP(max(T-tau_e,0))-lambda*sum_FP(max(T-tau_f,0))",
        "lambda_primary": 1,
        "lambda_sensitivity": [0, 2],
        "duplicate_reward": 0,
        "late_reward": 0,
        "committed_set_mutability": "append_only; event identity and interval fixed atomically at commit",
        "primary_metrics": ["AnytimeAUC_F1", "time_weighted_unique_event_utility", "TTFC", "unique_committed_events_at_T", "event_precision_at_T", "event_recall_at_T"],
        "mechanism_metrics": ["duplicate_CONFIRM_rate", "under_merge_rate", "over_merge_event_loss", "SCAN_starvation_duration", "frontier_congestion_duration", "unused_safe_deadline", "STOP_time"],
        "rollout_metrics": ["planning_invocation_count", "planning_time", "planning_time_over_deadline", "fallback_trigger_rate", "incorrect_rollout_override_rate", "advantage_interval_width"],
        "safety_metrics": ["deadline_miss", "unfinished_action_at_T", "uncommitted_positive_counted_as_output", "future_proxy_access"],
        "planning_cost_semantics": "planning consumes wall-clock while durable utility is constant; compare plan-then-act using net planning-aware value",
        "perfect_oracle_simplification": "If H-ROLLOUT1A has no FP, the FP term is zero and lambda does not affect results; registry remains unchanged.",
        "final_metric_equivalence": False,
    }
    write_json(OUT / "UTILITY_REGISTRY.json", utility)

    write(DOC / "00_AUTHORITY_AND_TERMINOLOGY.md", f"""
# Authority and terminology freeze

Status: `FROZEN_RESULT_BLIND`. Generated {created}. No toy comparison, physical call, GPU extraction, or held-out-real-data access was performed.

## Authority order and observed state

The user-supplied D1--D4 freeze specification governs this package. It is interpreted with the repository contracts, registries, ledgers, failure catalog, two-video NO_GO report, Stage-A model report, H-DS1 deadline artifacts, and frozen unit manifest. Their SHA-256 values are recorded in the freeze manifest.

Observed evidence: the rule-based two-video route is `NO_GO`; FIFO is the current simple baseline; M0 is exploratory and not deployable; the temporal refiner shows no clear gain; H-DS1 is empirical development safety, not WCET; no toy rollout evidence exists. Derived decision: only design/preregistration is authorized. Working hypothesis: ideal symmetric rollout may improve a proper base policy under restrictive exact-model conditions. Unresolved: a full pre-action SCAN obligation bound.

## Frozen terms

- **Candidate Witness**: runtime-visible proxy evidence tied immutably to one VERIFY opportunity. It is not an oracle label or event.
- **Event Hypothesis**: a frontier group containing one or more witnesses believed to concern one event opportunity; grouping can under-merge or over-merge.
- **Committed Event**: an event interval durably and atomically materialized into the append-only output snapshot after CONFIRM.
- **Event-Hypothesis Frontier**: current hypotheses and their witness states, not committed output.
- **VERIFY**: physical semantic Oracle plus parser only.
- **CONFIRM**: VERIFY, PARSE, MATERIALIZE, ATOMIC durable COMMIT, then frontier update as one decision-level action.
- **Scan State** replaces “coverage”; **Ratio-PSVR baseline** replaces “ratio-index”; **Committed Event** replaces “confirmed result”.

The three entities are not one-to-one: many witnesses may represent one event; under-merge may create several hypotheses for one event; over-merge may put several events in one hypothesis; a positive witness may duplicate an existing committed event or fail materialization; and one hypothesis may yield no committed event.

`H-PROG1` is superseded as the method direction by `H-ROLLOUT1` but remains a baseline. “M0 candidate value” means an optional confirm-outcome estimator only, never a rollout world model or a dependency of H-ROLLOUT1A.

SAFE_HARBOR means stop starting work and return the last complete durable snapshot. It never flushes dirty state.
""")

    write(DOC / "01_D1_UTILITY_REGISTRY.md", """
# D1 — Utility registry

Status: `COMPLETE_FROZEN`.

The main problem starts with an empty committed set, so `u(0)=0`. The general staircase identity may contain `u(0)T`, but that term is identically zero here and is not a design contribution. If commits occur at `0<t_1<...<t_K<=T`, with `Delta u_k=u(t_k+)-u(t_k-)`, then

`integral_0^T u(t)dt = sum_k Delta u_k (T-t_k)`.

This holds for any durable staircase utility. It does not make rewards state-independent: for F1, each increment depends on the entire committed set.

The algorithm surrogate is `sum_e in TP (T-tau_e)_+ - lambda sum_f in FP (T-tau_f)_+`, with primary `lambda=1` and preregistered auxiliary sensitivities `0,2`. `tau` is first durable commit time. Duplicate reward and post-deadline reward are zero. The committed set is append-only; identity, interpretation, and interval cannot be revised, revoked, or post-hoc merged. Boundary enhancement is excluded.

The surrogate is not the paper metric. Primary evaluation is AnytimeAUC_F1, time-weighted unique-event utility, TTFC, unique events, precision, and recall; mechanism, rollout, and safety diagnostics are enumerated in `UTILITY_REGISTRY.json`.

Planning changes no committed state while it runs. Its duration shortens the remaining horizon, so it is charged naturally through AUC; rollout admission and action choice must use net planning-aware value rather than a cost-free value followed by feasibility alone.
""")

    base = {
        "spec_id": "PSVR_SHIELDED_BASE_POLICY_V1",
        "status": "BLOCKED_NUMERIC_BINDING",
        "logical_spec_status": "COMPLETE",
        "executable_physical_binding": False,
        "state": ["scan_state", "event_hypothesis_frontier", "committed_events", "execution_mode", "frozen_query", "remaining_wall_clock"],
        "actions": ["SCAN(region)", "CONFIRM(hypothesis,witness)", "STOP"],
        "confirm_atomic_sequence": ["VERIFY", "PARSE", "MATERIALIZE", "ATOMIC_COMMIT", "FRONTIER_UPDATE"],
        "safe_harbor": "STOP_STARTING_NEW_WORK_AND_RETURN_LAST_COMPLETE_DURABLE_SNAPSHOT",
        "tie_break": ["hypothesis_created_at", "hypothesis_id", "witness_created_at", "witness_id"],
        "tie_break_version": "GROUP_FIFO_V1",
        "forbidden_inputs": ["future_proxy", "unscanned_content", "reference_labels", "future_oracle_outcome", "evaluator_bottleneck_label", "rollout_result", "m0_prediction", "latent_event_id"],
        "scan_iterator": {
            "order": "ascending (start_time, end_time, unit_id)",
            "region_duration_seconds": "10 nominal; final manifest row may be 5",
            "region_overlap_seconds": "manifest-defined; rows 345/346 overlap 2.07 seconds, so no false zero-overlap claim",
            "region_ids": "unit_id 0..346",
            "seek_decode_convention": "manifest start_frame/end_frame inclusive; media timestamps authoritative; 5 proxy FPS",
            "source_revision_sha256": source_hashes["scan_runtime"],
            "manifest_path": str(SOURCE["unit_manifest"].relative_to(ROOT)),
            "manifest_sha256": source_hashes["unit_manifest"],
            "config_sha256": source_hashes["proxy_cost"],
        },
        "numeric_binding": {
            "REGION_DURATION": "10 seconds nominal; final row 5 seconds",
            "REGION_OVERLAP": "manifest-defined; maximum observed 2.07 seconds at final boundary",
            "SCAN_ITERATOR_MANIFEST": source_hashes["unit_manifest"],
            "CONFIRM_WITNESS_DURATION": "unit-manifest interval: 10 seconds nominal; 5 seconds final row",
            "ALPHA_SCAN": None,
            "ALPHA_CONFIRM": None,
            "TOTAL_SCAN_BOUND": None,
            "TOTAL_CONFIRM_BOUND": confirm_upper,
            "STANDARD_CONFIRM_RESERVE": confirm_upper,
            "MIN_ACTION_DURATION": None,
            "TIE_BREAK_VERSION": "GROUP_FIFO_V1",
        },
        "confirm_binding_evidence": {
            "verify_upper_seconds": action_upper,
            "durable_commit_upper_seconds": commit_upper,
            "guard_required_sum_seconds": confirm_upper,
            "scope": "empirical one-video/one-query/one-A800 workload; not WCET",
            "action_profile_sha256": source_hashes["action_profile"],
            "commit_profile_sha256": source_hashes["commit_profile"],
        },
        "blocking_fields": {
            "TOTAL_SCAN_BOUND": "No direct calibrated pre-action full-obligation SCAN bound exists.",
            "ALPHA_SCAN": "Cannot bind until the full SCAN duration distribution is calibrated.",
            "ALPHA_CONFIRM": "Separate marginal alpha=0.1 profiles do not establish alpha=0.1 for their summed complete CONFIRM obligation; direct paired calibration is required.",
            "MIN_ACTION_DURATION": "No certified strictly positive lower bound across complete SCAN and CONFIRM actions exists.",
        },
        "rejected_numeric_substitute": {
            "legacy_scan_formula_seconds": legacy_scan_formula,
            "reason": "Derived from per-frame p95 and an additive allowance, then updated after action completion; not a direct full-obligation pre-action bound and cannot be relabeled as B_S."
        },
        "properness_rank": "finite lexicographic rank: unscanned regions plus nonterminal witnesses; SCAN consumes one of 347 regions, CONFIRM terminalizes its witness, and every region emits finitely many witnesses",
        "f_min_role": ["logging", "stratified_analysis", "plan_admission_candidate_feature", "world_model_feature", "alerting"],
        "f_min_forbidden_roles": ["force_SCAN", "veto_safe_CONFIRM", "override_rollout"],
        "fail_closed_when_scan_binding_missing": True,
    }
    write_json(OUT / "BASE_POLICY_SPEC.json", base)

    write(DOC / "02_D2_SHIELDED_BASE_POLICY.md", f"""
# D2 — Safety-shielded base policy pi0

Status: `LOGICAL_SPEC_COMPLETE`; numeric status: `BLOCKED_NUMERIC_BINDING`; physically executable freeze: **no**.

## State, actions, and ordering

`x_t=(I_t,rho_t)`, where `I_t=(C_t,H_t,E_t,m_t,q)` contains scan state, Event-Hypothesis Frontier, durable events, runtime mode, and frozen query, and `rho_t=T-t`. Actions are SCAN(region), atomic CONFIRM(h,w), and STOP. Only CONFIRM can modify committed output; no decision boundary exposes dirty confirmed state. SAFE_HARBOR returns the last complete durable snapshot without flushing.

Hypotheses sort by `(hypothesis_created_at,hypothesis_id)` and witnesses within them by `(witness_created_at,witness_id)`. Scores, M0, labels, future information, and rollout results cannot alter this order. The deterministic scan iterator sorts the frozen public manifest by `(start_time,end_time,unit_id)`; it uses 10-second nominal units and the manifest's explicit final boundary. Exact hashes are in `BASE_POLICY_SPEC.json`.

## Total decision rule

Let `P_C(x)={{(h,w): w is unverified and not pending, B_C(x,h,w)<=rho}}`. If nonempty, CONFIRM the first group-FIFO pair. Otherwise SCAN the next region only if `B_S(x,r)+R_C<=rho`. Otherwise STOP. A missing bound is not infinity or a guessed default: it makes that action inadmissible. Thus the logical function is defined everywhere, deterministic, standalone, non-anticipatory, deadline-aware, learned-estimator-free, and near-zero overhead.

`z_F=(|H|,s_max,s_median,rho)` is logging/analysis/admission/model/alerting data only. It cannot force SCAN, veto safe CONFIRM, or override rollout.

## Cost and safety audit

Complete costs must include selection, switching, queue, seek/decode, proxy/tracking, Oracle, parse, materialize, snapshot, commit, and frontier update. The frozen H-DS1 guard supplies a stricter operational CONFIRM reserve: `{action_upper:.10f}+{commit_upper:.10f}={confirm_upper:.10f}` seconds. It is a sum of two operational upper estimators, not a calibrated 0.9 quantile of complete `D_C`; `ALPHA_CONFIRM` is therefore unbound. Paired traces give empirical development evidence for one video/query/A800 workload, not WCET, a formal coverage level, or zero-miss theory.

The existing SCAN admission formula is `{legacy_scan_formula:.10f}` seconds before a separate commit reserve. It derives from a per-frame p95, multiplies it by 50, adds an allowance, and adapts after observing completed SCAN wall time. It is not a directly calibrated pre-action full-obligation `B_S`; treating it as one would commit the prohibited phase-quantile/composition error. Therefore `TOTAL_SCAN_BOUND`, `ALPHA_SCAN`, and a certified global `MIN_ACTION_DURATION` remain blocking fields.

## Properties and proof obligations

- Conditional deadline safety: if every admitted action duration is at most its certified complete bound and admission requires bound `<=rho`, completion occurs by T. For SCAN, reserving `R_C` additionally leaves one standard CONFIRM slot. This theorem cannot currently be instantiated because `B_S` is missing.
- Empirical chance safety: calibrated quantiles support only workload-scoped empirical chance claims; H-DS1's 0/13 misses is validation evidence, not a formal zero-miss guarantee.
- Properness has two proofs. Under the requested positive-duration premise, at most `ceil(T/d_min)` non-STOP actions occur, but numeric `d_min` is unbound. Independently, a finite lexicographic rank decreases: SCAN consumes one of 347 regions and emits finitely many witnesses; CONFIRM terminalizes at least its selected witness. Thus logical termination does not rely on the missing numeric lower bound.
- Non-anticipation follows because the rule is a function only of runtime-visible `x_t` and fixed profiles.
- Evidence honesty follows from append-only state transitions: SCAN and STOP leave `E_t` unchanged; only completed atomic CONFIRM may replace it with `E_t union {{e}}`.

The focused pure unit tests cover all mandated action cases, deterministic tie-breaking, future-field rejection, and fail-closed missing binding.
""")

    dev_seeds = list(range(11000, 11128))
    held_seeds = list(range(91000, 91512))
    def fixture(name, horizon, scan_costs, confirm_costs, events, initial, emissions, groups, invariant):
        return {
            "scenario_id": name, "primary_inference": False, "horizon_seconds": horizon,
            "regions": [{"region_id": f"r{i}", "interval": [10*i, 10*(i+1)], "scan_cost_seconds": cost} for i, cost in enumerate(scan_costs)],
            "latent_events": events, "initial_frontier_witnesses": initial,
            "scan_emissions": emissions, "confirm_cost_seconds_by_witness": confirm_costs,
            "initial_hypothesis_members": groups, "oracle": "perfect", "materialization": "perfect",
            "group_closure": "confirming any member closes its hypothesis and suppresses remaining members",
            "required_behavioral_invariant": invariant,
        }
    ev = lambda eid, region, start, end: {"event_id": eid, "region_id": region, "interval": [start, end], "actor_id": f"actor_{eid}"}
    wit = lambda wid, eid, score, created=0: {"witness_id": wid, "latent_event_id": eid, "raw_score": score, "creation_time": created, "query_id": "q", "interval": [created, created + 1]}
    named = {
        "spec_id": "PSVR_TOY_NAMED_SCENARIOS_V1",
        "status": "FROZEN_DIAGNOSTIC_ONLY",
        "common": {"region_duration_seconds": 10, "planning_cost_seconds": 0, "tie_break": "GROUP_FIFO_V1", "committed_set_initial": [], "policy_projection_removes": ["latent_event_id", "latent_events", "required_behavioral_invariant"]},
        "scenarios": [
            fixture("VERIFY_FIRST_FAILURE", 8, [2,2,2], {"w_neg":4,"w_e":2}, [ev("e1","r1",11,13)], [wit("w_neg",None,0.95)], {"r0":[],"r1":[wit("w_e","e1",0.8,2)],"r2":[]}, {"h_neg":["w_neg"]}, "CONFIRM(w_neg) first leaves insufficient time for SCAN(r1)+CONFIRM(w_e); SCAN(r1) first can commit e1"),
            fixture("SCAN_FIRST_FAILURE", 6, [5,5], {"w_e":2}, [ev("e1","r0",1,3)], [wit("w_e","e1",0.9)], {"r0":[],"r1":[]}, {"h_e":["w_e"]}, "SCAN first leaves insufficient time for CONFIRM(w_e); CONFIRM first commits e1"),
            fixture("FIXED_PERIODIC_FAILURE", 13, [2,2,2,2], {"w1":3,"w2":3}, [ev("e1","r0",1,2),ev("e2","r3",31,32)], [], {"r0":[wit("w1","e1",0.8,2)],"r1":[],"r2":[],"r3":[wit("w2","e2",0.8,8)]}, {}, "k=2 fixed periodic delays w1 relative to immediate CONFIRM and cannot both preserve its timing and reach/confirm w2"),
            fixture("CAPACITY_MATCHING_LOW_QUALITY_FAILURE", 12, [2,2,2], {"n1":3,"n2":3,"e1w":3}, [ev("e1","r2",21,23)], [wit("n1",None,0.9),wit("n2",None,0.8)], {"r0":[],"r1":[],"r2":[wit("e1w","e1",0.7,2)]}, {"h_n1":["n1"],"h_n2":["n2"]}, "frontier-count capacity is satisfied by two negatives although productive SCAN(r2) exposes the only event"),
            fixture("SINGLE_HIGH_VALUE_FRONTIER", 5, [4], {"e1w":2}, [ev("e1","r0",1,2)], [wit("e1w","e1",0.99)], {"r0":[]}, {"h_e1":["e1w"]}, "CONFIRM(e1w) is safe and SCAN cannot leave the standard confirm reserve"),
            fixture("DUPLICATE_HEAVY_FRONTIER", 12, [3], {"w1":2,"w2":2,"w3":2,"w4":2}, [ev("e1","r0",1,4)], [wit("w1","e1",0.9),wit("w2","e1",0.85),wit("w3","e1",0.8),wit("w4","e1",0.75)], {"r0":[]}, {"h1":["w1"],"h2":["w2"],"h3":["w3"],"h4":["w4"]}, "only first durable commit of e1 earns utility; later positive confirms are duplicates with zero reward"),
            fixture("LATE_HORIZON_CLOSURE", 4, [3], {"e1w":5}, [ev("e1","r0",1,2)], [wit("e1w","e1",0.9)], {"r0":[]}, {"h_e1":["e1w"]}, "unsafe CONFIRM is not started; SAFE_HARBOR returns the empty durable snapshot"),
            fixture("HETEROGENEOUS_CONFIRM_COST", 8, [3], {"slow":7,"fast":2}, [ev("e1","r0",1,2),ev("e2","r0",3,4)], [wit("slow","e1",0.9),wit("fast","e2",0.9)], {"r0":[]}, {"h_slow":["slow"],"h_fast":["fast"]}, "equal-quality witnesses have unequal opportunity cost; continuation evaluation must retain complete per-witness costs"),
            fixture("DENSE_HOMOGENEOUS_BASELINE_FAVORABLE", 18, [2,2,2], {"w1":2,"w2":2,"w3":2}, [ev("e1","r0",1,2),ev("e2","r1",11,12),ev("e3","r2",21,22)], [], {"r0":[wit("w1","e1",0.9,2)],"r1":[wit("w2","e2",0.9,6)],"r2":[wit("w3","e3",0.9,10)]}, {}, "homogeneous FIFO immediate confirms are a permitted best case and any pi0 win must be reported"),
            fixture("BURSTY_SCAN_FAVORABLE", 14, [2,2,2,2], {"w1":2,"w2":2,"w3":2}, [ev("e1","r2",21,22),ev("e2","r2",23,24),ev("e3","r3",31,32)], [wit("n0",None,0.95)], {"r0":[],"r1":[],"r2":[wit("w1","e1",0.8,6),wit("w2","e2",0.8,6)],"r3":[wit("w3","e3",0.8,10)]}, {"h_n0":["n0"]}, "productive scans into the burst can dominate immediate confirmation of the initial negative"),
        ],
    }
    write_json(OUT / "TOY_NAMED_SCENARIOS.json", named)
    named_hash = sha(OUT / "TOY_NAMED_SCENARIOS.json")
    construction = {
        "spec_id": "PSVR_TOY_CONSTRUCTION_V1",
        "status": "FROZEN_RESULT_BLIND",
        "arithmetic": "IEEE-754 binary64, round-to-nearest ties-to-even; integer operations unsigned modulo 2^64",
        "rng": {
            "algorithm": "SplitMix64",
            "state_initialization": "state=seed mod 2^64",
            "next_uint64": [
                "state=(state+0x9E3779B97F4A7C15) mod 2^64",
                "z=state; z=(z xor (z>>30))*0xBF58476D1CE4E5B9 mod 2^64",
                "z=(z xor (z>>27))*0x94D049BB133111EB mod 2^64",
                "return z xor (z>>31)",
            ],
            "uniform_open_0_1": "U=(next_uint64+0.5)/2^64",
            "bernoulli": "1 iff U<p",
            "uniform": "a+(b-a)*U",
            "log_uniform": "exp(log(a)+(log(b)-log(a))*U)",
            "categorical": "first ordered category whose cumulative probability is >= U; last category absorbs rounding",
            "poisson": "inverse CDF: start k=0,p=exp(-lambda),cdf=p; while U>cdf increment k and p*=lambda/k, cdf+=p",
            "fixture_seed": 1,
            "fixture_first_uint64": splitmix64_sequence(1, 8),
        },
        "seed_mapping": {
            "development": {"ordered_seeds": dev_seeds, "split_index": "zero-based position in ordered_seeds"},
            "heldout": {"ordered_seeds": held_seeds, "split_index": "zero-based position in ordered_seeds"},
            "process_assignment": "[UNIFORM_SPARSE,UNIFORM_DENSE,BURSTY_CLUSTERED][split_index mod 3]",
            "cost_regime_assignment": "[SCAN_CHEAP,BALANCED,SCAN_EXPENSIVE][floor(split_index/3) mod 3]",
        },
        "ordered_draw_schedule": [
            "M categorical draw", "event_density log-uniform draw", "candidate_quality uniform draw",
            "duplicate_factor log-uniform draw", "cost_variance uniform draw",
            "under_merge_rate uniform draw", "over_merge_rate uniform draw",
            "hard_negative_rate uniform draw", "horizon_grid categorical draw",
            "event_count Poisson draw", "cluster_count and centers if bursty",
            "for each event in event_id order: placement, length, actor, detectability, multiplicity",
            "for each region in region_id order: activity, event witness emissions, hard-negative count and witnesses",
            "group witnesses in witness_id order", "draw realized action costs lazily in action-ledger order",
        ],
        "split_parameters": {
            "development": {
                "M": {"values": [16, 32, 64], "weights": [0.25, 0.5, 0.25]},
                "density_by_process": {"UNIFORM_SPARSE": [0.005, 0.03], "UNIFORM_DENSE": [0.08, 0.20], "BURSTY_CLUSTERED": [0.02, 0.12]},
                "candidate_quality": [0.10, 0.75], "duplicate_factor": [1.0, 6.0],
                "cost_variance": [0.0, 0.6], "under_merge_rate": [0.0, 0.25],
                "over_merge_rate": [0.0, 0.18], "hard_negative_rate": [0.0, 0.35],
            },
            "heldout": {
                "M": {"values": [16, 32, 64], "weights": [0.25, 0.5, 0.25]},
                "density_by_process": {"UNIFORM_SPARSE": [0.003, 0.04], "UNIFORM_DENSE": [0.06, 0.25], "BURSTY_CLUSTERED": [0.015, 0.15]},
                "candidate_quality": [0.05, 0.80], "duplicate_factor": [1.0, 8.0],
                "cost_variance": [0.0, 0.8], "under_merge_rate": [0.0, 0.35],
                "over_merge_rate": [0.0, 0.25], "hard_negative_rate": [0.0, 0.50],
            },
        },
        "geometry_and_horizon": {
            "region_duration_seconds": 10.0, "region_overlap_seconds": 0.0,
            "regions": "r000..r(M-1), interval [10j,10(j+1))",
            "horizon_confirm_cost_units": [1.25, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32],
            "horizon_weights": [1/11] * 11,
            "absolute_confirm_base_seconds": 5.0,
        },
        "event_kernel": {
            "count": "Poisson(M*event_density)",
            "uniform_placement": "region=floor(M*U), start=10*region+10*U",
            "bursty_placement": "C=1+Poisson(1); centers=floor(M*U); choose center categorical-uniform; offset=clip(floor(4*(U1+U2-1)),-4,4)",
            "length_seconds": "min(remaining_media, exp(log(0.5)+(log(40)-log(0.5))*U))",
            "region_membership": "all half-open regions intersecting [start,start+length)",
            "actor_count": {"values": [1, 2, 3], "weights": [0.75, 0.20, 0.05]},
            "actor_id": "actor_%04d using categorical actor index within episode",
            "detectability": "clip(candidate_quality+0.25*(2U-1),0.01,0.99)",
            "candidate_multiplicity": "1+Poisson(duplicate_factor-1)",
        },
        "candidate_kernel": {
            "region_activity": "uniform(0.5,2.0)",
            "true_emission": "for each event multiplicity trial whose event intersects region, emit iff Bernoulli(detectability)",
            "hard_negative_count": "Poisson(hard_negative_rate*region_activity)",
            "true_raw_score": "candidate_quality+(1-candidate_quality)*U",
            "negative_raw_score": "(1-candidate_quality)*U",
            "interval_jitter": "add uniform(-1,1) seconds independently to both endpoints, sort, clip to media",
            "proxy_feature_vector": "[raw_score, interval_midpoint/media_duration, interval_length/40, region_activity/2]",
            "witness_id": "w_<region_index:04d>_<within_region_index:04d>",
            "latent_event_id": "event id for true witness, null for hard negative; removed from policy projection",
        },
        "grouping_kernel": {
            "initial": "true witnesses partition by latent_event_id; each hard negative starts alone",
            "under_merge": "after first witness of each true event, each later witness starts a new hypothesis iff Bernoulli(under_merge_rate)",
            "over_merge": "scan hypotheses by creation order in adjacent nonoverlapping pairs; merge pair iff Bernoulli(over_merge_rate)",
            "hypothesis_id": "h_<minimum member witness_id>",
            "irrecoverable_loss": "after any witness in an over-merged hypothesis is CONFIRMed, close the hypothesis and suppress all remaining members; suppressed distinct latent events are lost",
        },
        "cost_kernel": {
            "ratio_by_regime": {"SCAN_CHEAP": [0.05, 0.30], "BALANCED": [0.30, 1.50], "SCAN_EXPENSIVE": [1.50, 5.00]},
            "ratio_draw": "log_uniform over assigned regime interval",
            "confirm_nominal_seconds": "5*(0.5+U), drawn once per witness",
            "scan_nominal_seconds": "5*ratio*(0.75+0.5*region_activity/2), drawn once per region",
            "realized_duration": "nominal*(1-v+2*v*Bernoulli(0.5)), v=cost_variance",
            "mode_switch_seconds": "0 for same/initial mode; 0.05*confirm_base_seconds otherwise",
            "complete_action_cost": "selection(0)+mode_switch+realized core cost; toy parse/materialize/snapshot/commit/frontier costs are included in confirm nominal, proxy/grouping in scan nominal",
            "planning_primary_seconds": 0.0,
            "planning_auxiliary_seconds": "c*confirm_base_seconds for c in [0.01,0.05,0.10,0.25], reported separately",
        },
        "confirm_kernel_H_ROLLOUT1A": {
            "oracle": "positive iff latent_event_id is non-null", "materialization_success": True,
            "duplicate": "positive latent_event_id already in committed set", "false_positive": False,
            "new_commit": "positive, not duplicate, full action completes by horizon",
            "commit_identity": "exact latent_event_id; committed interval equals latent interval",
        },
        "visibility_projection": {
            "policy_visible": ["scanned region metadata", "witness fields except latent_event_id", "hypothesis membership", "committed events", "remaining time", "past actions and durations"],
            "removed_recursively": ["latent_events", "latent_event_id", "unscanned emissions", "future_cost_draws", "future_oracle_draws", "regime family", "clairvoyant value"],
        },
        "canonicalization": "UTF-8 JSON, sorted keys, separators comma/colon, no NaN/Infinity; episode fixture hash is SHA-256 of canonical bytes",
        "named_scenarios": {"path": "outputs/psvr_rollout_preimplementation/TOY_NAMED_SCENARIOS.json", "sha256": named_hash, "count": 10, "excluded_from_split_seed_construction_and_primary_aggregation": True},
    }
    write_json(OUT / "TOY_CONSTRUCTION_SPEC.json", construction)
    toy_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:garc:psvr:toy-environment:v1",
        "title": "PSVR finite-horizon SMDP episode",
        "type": "object",
        "required": ["episode_id", "seed", "horizon_seconds", "regions", "latent_events", "cost_process", "grouping", "oracle", "planning"],
        "properties": {
            "episode_id": {"type": "string", "minLength": 1},
            "seed": {"type": "integer"},
            "horizon_seconds": {"type": "number", "exclusiveMinimum": 0},
            "regions": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/region"}},
            "latent_events": {"type": "array", "items": {"$ref": "#/$defs/event"}},
            "cost_process": {"$ref": "#/$defs/cost"},
            "grouping": {"type": "object", "required": ["under_merge_rate", "over_merge_rate", "over_merge_suppression_loss"], "properties": {"under_merge_rate": {"type": "number", "minimum": 0, "maximum": 1}, "over_merge_rate": {"type": "number", "minimum": 0, "maximum": 1}, "over_merge_suppression_loss": {"type": "boolean"}}, "additionalProperties": False},
            "oracle": {"type": "object", "required": ["true_positive_rate", "false_positive_rate", "materialization_success_rate"], "properties": {"true_positive_rate": {"type": "number", "minimum": 0, "maximum": 1}, "false_positive_rate": {"type": "number", "minimum": 0, "maximum": 1}, "materialization_success_rate": {"type": "number", "minimum": 0, "maximum": 1}}, "additionalProperties": False},
            "planning": {"type": "object", "required": ["mode", "duration_distribution"], "properties": {"mode": {"enum": ["IDEAL_ZERO", "PARAMETRIC"]}, "duration_distribution": {"$ref": "#/$defs/distribution"}}, "additionalProperties": False},
        },
        "$defs": {
            "distribution": {"type": "object", "required": ["family", "parameters"], "properties": {"family": {"enum": ["CONSTANT", "TWO_POINT", "POISSON", "CATEGORICAL"]}, "parameters": {"type": "object", "minProperties": 1, "properties": {"value": {"type": "number"}, "lambda": {"type": "number", "minimum": 0}, "low": {"type": "number"}, "high": {"type": "number"}, "values": {"type": "array"}, "probabilities": {"type": "array"}}, "additionalProperties": False}}, "additionalProperties": False},
            "region": {"type": "object", "required": ["region_id", "media_start", "media_end", "latent_event_ids", "scan_duration_distribution", "candidate_emission", "hard_negative_process"], "properties": {"region_id": {"type": "string"}, "media_start": {"type": "number", "minimum": 0}, "media_end": {"type": "number", "exclusiveMinimum": 0}, "latent_event_ids": {"type": "array", "items": {"type": "string"}}, "scan_duration_distribution": {"$ref": "#/$defs/distribution"}, "candidate_emission": {"type": "object", "required": ["candidate_quality", "duplicate_factor", "region_activity"], "properties": {"candidate_quality": {"type": "number", "minimum": 0, "maximum": 1}, "duplicate_factor": {"type": "number", "minimum": 1}, "region_activity": {"type": "number", "minimum": 0}}, "additionalProperties": False}, "hard_negative_process": {"type": "object", "required": ["rate"], "properties": {"rate": {"type": "number", "minimum": 0}}, "additionalProperties": False}}, "additionalProperties": False},
            "event": {"type": "object", "required": ["event_id", "query_id", "region_ids", "interval", "actor_id", "detectability", "candidate_multiplicity", "confirm_characteristics"], "properties": {"event_id": {"type": "string"}, "query_id": {"type": "string"}, "region_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}}, "interval": {"type": "array", "prefixItems": [{"type": "number"}, {"type": "number"}], "minItems": 2, "maxItems": 2}, "actor_id": {"type": "string"}, "detectability": {"type": "number", "minimum": 0, "maximum": 1}, "candidate_multiplicity": {"$ref": "#/$defs/distribution"}, "confirm_characteristics": {"type": "object", "required": ["nominal_duration_seconds"], "properties": {"nominal_duration_seconds": {"type": "number", "exclusiveMinimum": 0}}, "additionalProperties": False}}, "additionalProperties": False},
            "witness": {"type": "object", "required": ["witness_id", "latent_event_id", "query_id", "actor_tracklet", "interval", "proxy_features", "raw_score", "creation_time", "confirm_duration_parameters"], "properties": {"witness_id": {"type": "string"}, "latent_event_id": {"type": ["string", "null"]}, "query_id": {"type": "string"}, "actor_tracklet": {"type": "object"}, "interval": {"type": "array"}, "proxy_features": {"type": "array", "items": {"type": "number"}}, "raw_score": {"type": "number"}, "creation_time": {"type": "number"}, "confirm_duration_parameters": {"type": "object"}}, "additionalProperties": False},
            "cost": {"type": "object", "required": ["scan", "confirm", "mode_switch", "planning", "variance_scale", "scan_confirm_ratio_regime"], "properties": {"scan": {"$ref": "#/$defs/distribution"}, "confirm": {"$ref": "#/$defs/distribution"}, "mode_switch": {"$ref": "#/$defs/distribution"}, "planning": {"$ref": "#/$defs/distribution"}, "variance_scale": {"type": "number", "minimum": 0}, "scan_confirm_ratio_regime": {"enum": ["SCAN_CHEAP", "BALANCED", "SCAN_EXPENSIVE"]}}, "additionalProperties": False},
        },
        "additionalProperties": False,
        "visibility_contract": {"policy_visible": ["scanned_region_ids", "emitted_witness_fields_except_latent_event_id", "hypothesis_assignments", "committed_events", "remaining_time", "action_history"], "latent_only": ["latent_events", "latent_event_id", "unscanned_emissions", "future_cost_draws", "future_oracle_draws"], "evaluator_only": ["reference_event_matching", "regime_family", "leakage_labels", "clairvoyant_value"]},
        "transition_contract": {"SCAN": ["consume full duration", "mark region scanned", "reveal proxy evidence", "emit zero or more witnesses", "group/update frontier", "never modify committed set"], "CONFIRM": ["consume full duration", "oracle result", "materialization result", "new/duplicate/false-positive classification", "atomic commit if new", "frontier suppression/update"], "STOP": ["return last durable snapshot"]},
    }
    write_json(OUT / "TOY_ENVIRONMENT_SCHEMA.json", toy_schema)

    construction_hash = sha(OUT / "TOY_CONSTRUCTION_SPEC.json")
    yaml = f"""schema_version: PSVR_TOY_PARAMETER_DISTRIBUTION_V1
status: FROZEN_RESULT_BLIND
sampling_unit: independent_latent_video_episode
construction_spec: outputs/psvr_rollout_preimplementation/TOY_CONSTRUCTION_SPEC.json
construction_spec_sha256: {construction_hash}
named_scenario_spec: outputs/psvr_rollout_preimplementation/TOY_NAMED_SCENARIOS.json
named_scenario_spec_sha256: {named_hash}
rng: SplitMix64_with_frozen_uint64_fixture
joint_sampler: ordered_draw_schedule_in_construction_spec
axes:
  event_density:
    family: LOG_UNIFORM
    units: expected_events_per_region
    development_by_process: {{UNIFORM_SPARSE: [0.005, 0.03], UNIFORM_DENSE: [0.08, 0.20], BURSTY_CLUSTERED: [0.02, 0.12]}}
    heldout_by_process: {{UNIFORM_SPARSE: [0.003, 0.04], UNIFORM_DENSE: [0.06, 0.25], BURSTY_CLUSTERED: [0.015, 0.15]}}
  burstiness:
    processes: [UNIFORM_SPARSE, UNIFORM_DENSE, BURSTY_CLUSTERED]
    assignment: split_index_mod_3
  candidate_quality:
    family: UNIFORM
    development_range: [0.10, 0.75]
    heldout_range: [0.05, 0.80]
  duplicate_factor:
    family: LOG_UNIFORM_THEN_1_PLUS_POISSON
    development_range: [1.0, 6.0]
    heldout_range: [1.0, 8.0]
  scan_confirm_cost_ratio:
    assignment: floor_split_index_over_3_mod_3
    regimes:
      SCAN_CHEAP: [0.05, 0.30]
      BALANCED: [0.30, 1.50]
      SCAN_EXPENSIVE: [1.50, 5.00]
  cost_variance:
    family: BOUNDED_TWO_POINT
    development_range: [0.0, 0.6]
    heldout_range: [0.0, 0.8]
  estimator_noise:
    H_ROLLOUT1A: 0.0
    reserved_schema_range: [0.0, 1.0]
  grouping_error:
    under_merge_rate_range: [0.0, 0.35]
    over_merge_rate_range: [0.0, 0.25]
    over_merge_causes_irrecoverable_suppression: true
event_process:
  M_categorical: {{values: [16, 32, 64], weights: [0.25, 0.50, 0.25]}}
  event_count: Poisson_M_times_event_density
  event_length_seconds: LOG_UNIFORM_[0.5,40]_clipped_to_media
  actor_count_categorical: {{1: 0.75, 2: 0.20, 3: 0.05}}
  hard_negative_rate_range: [0.0, 0.50]
  region_activity_multiplier_range: [0.5, 2.0]
oracle_materialization:
  H_ROLLOUT1A: {{true_positive_rate: 1.0, false_positive_rate: 0.0, materialization_success_rate: 1.0}}
  H_ROLLOUT1B_reserved: {{true_positive_rate_range: [0.8, 1.0], false_positive_rate_range: [0.0, 0.2], materialization_success_rate_range: [0.8, 1.0]}}
planning:
  primary: {{mode: IDEAL_ZERO, seconds: 0.0}}
  auxiliary_parametric: {{family: CONSTANT, seconds_over_confirm_cost: [0.01, 0.05, 0.10, 0.25]}}
horizon_rule:
  T_floor: smallest preregistered grid horizon at which any non-clairvoyant baseline can complete one SCAN plus one CONFIRM under that episode's nominal costs
  T_saturation: smallest preregistered grid horizon at which Scan-Then-Confirm reaches at least 0.99 of the DP ceiling in expected primary utility
  no_saturation_rule: if no grid point reaches 0.99, set status NO_SATURATION_WITHIN_GRID and report outside Gate C; never extrapolate or alter grid
  T_transition: geometric mean of finite T_floor and T_saturation; status NO_TRANSITION and report outside Gate C if either is unavailable or floor >= saturation
  horizon_grid_confirm_cost_units: [1.25, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32]
splits:
  development:
    seeds: {dev_seeds}
    use: implementation correctness and informal debugging only
  heldout:
    seeds: {held_seeds}
    use: H-ROLLOUT1A primary decision; do not run without later explicit authorization
  seed_universes_disjoint: true
  parameter_distributions_distinct_and_frozen: true
named_scenarios:
  - VERIFY_FIRST_FAILURE
  - SCAN_FIRST_FAILURE
  - FIXED_PERIODIC_FAILURE
  - CAPACITY_MATCHING_LOW_QUALITY_FAILURE
  - SINGLE_HIGH_VALUE_FRONTIER
  - DUPLICATE_HEAVY_FRONTIER
  - LATE_HORIZON_CLOSURE
  - HETEROGENEOUS_CONFIRM_COST
  - DENSE_HOMOGENEOUS_BASELINE_FAVORABLE
  - BURSTY_SCAN_FAVORABLE
named_scenarios_in_primary_inference: false
"""
    write(OUT / "TOY_PARAMETER_DISTRIBUTION.yaml", yaml)

    write(DOC / "03_D3_TOY_GENERATIVE_MODEL.md", """
# D3 — Toy generative model

Status: `COMPLETE_FROZEN_SPECIFICATION`; no policy-quality run is authorized or produced.

The environment is a finite-horizon SMDP. It stores full latent state, exposes only a runtime information state to policies, and separately exposes evaluator-only truth after execution. `TOY_ENVIRONMENT_SCHEMA.json` freezes these boundaries. `TOY_CONSTRUCTION_SPEC.json` freezes SplitMix64, a conformance fixture, binary64 arithmetic, seed indexing, the complete ordered draw schedule, marginal and joint laws, geometry, absolute costs, transition kernels, identifiers, canonicalization, and visibility projection. A seed therefore identifies one episode rather than an implementation-dependent family of possible episodes.

Each episode has M media regions with latent events, complete SCAN cost distributions, candidate emission, and background hard negatives. Latent locations use `UNIFORM_SPARSE`, `UNIFORM_DENSE`, or `BURSTY_CLUSTERED`; event fields include query, region membership, interval, actor, detectability, multiplicity, and CONFIRM characteristics. A witness carries immutable identity, nullable latent event ID (environment-only), query, actor/tracklet, interval, proxy vector, raw score, creation time, and CONFIRM-cost parameters. Policy projections delete `latent_event_id`.

SCAN marks one region scanned, reveals proxy evidence, emits zero or more witnesses as a function of detectability, candidate quality, hard negatives, duplicates, and activity, updates grouping, consumes its complete random cost, and never commits. Under-merge splits one event's witnesses; over-merge combines different events and can irreversibly suppress later opportunities after one group is closed. This is structural opportunity loss, not score noise.

CONFIRM emits Oracle sign, materialization success/failure, new/duplicate/false-positive result, suppression/update, and complete duration. H-ROLLOUT1A fixes perfect Oracle/materialization but the schema retains H-ROLLOUT1B error fields. Costs include SCAN, CONFIRM, variance, switching, and planning. The three cost-ratio regimes and all eight requested axes are frozen in YAML. Primary planning cost is zero; parametric planning cost is auxiliary only.

Development and held-out seed universes are fixed, disjoint, and hash-bound; their parameter distributions are separately explicit. Construction conformance requires the frozen RNG uint64 fixture and, after implementation, canonical seed-to-episode fixture hashes before any policy comparison. `TOY_NAMED_SCENARIOS.json` fixes all ten diagnostic states, costs, witnesses, groups, emissions, horizons, and invariants; they cannot enter primary inference. Parameterized draws—not selected hand cases—define held-out evidence.
""")

    write(DOC / "06_COUNTEREXAMPLE_AND_EDGE_CASE_CATALOG.md", """
# Counterexample and edge-case catalog

These are frozen diagnostic scenarios, never primary statistical units. The table is explanatory; exact horizons, region states/costs, latent events, witnesses, emissions, hypothesis membership, and invariants are machine-bound in `outputs/psvr_rollout_preimplementation/TOY_NAMED_SCENARIOS.json`.

| Scenario | Construction | Prediction / invariant |
|---|---|---|
| VERIFY_FIRST_FAILURE | low-quality early frontier, productive unseen burst | always-CONFIRM loses discoverable events |
| SCAN_FIRST_FAILURE | one safe high-value witness, expensive next scan | always-SCAN delays or loses its commit |
| FIXED_PERIODIC_FAILURE | irregular burst/cost timing | fixed cadence mismatches opportunity |
| CAPACITY_MATCHING_LOW_QUALITY_FAILURE | frontier fills with hard negatives | capacity alone over-verifies low quality |
| SINGLE_HIGH_VALUE_FRONTIER | one unique witness, short horizon | symmetric evaluation retains immediate CONFIRM option |
| DUPLICATE_HEAVY_FRONTIER | many witnesses for one event | duplicate reward remains zero |
| LATE_HORIZON_CLOSURE | remaining time near action bounds | shield stops; no unfinished action counted |
| HETEROGENEOUS_CONFIRM_COST | equal success, unequal costs | continuation value may favor cheaper CONFIRM |
| DENSE_HOMOGENEOUS_BASELINE_FAVORABLE | dense equal-quality events | pi0 may match or beat rollout and must be reported |
| BURSTY_SCAN_FAVORABLE | unseen clustered events | SCAN can beat immediate CONFIRM |

Additional edges: zero events, zero candidates, all unsafe witnesses, exhausted iterator, simultaneous creation ties, last action exactly fits (`<=` admissible), duration exceeding a stochastic bound (record miss, never truncate), over-merged group closing two events (count opportunity loss), materialization failure (no commit), false positive (negative surrogate increment), duplicate positive (zero increment), and planning consuming the residual horizon.

Falsification checks: if VERIFY_FIRST and SCAN_FIRST do not reverse the corresponding fixed policy ranking, transition logic is suspect; if over-merge cannot lose an event, grouping is underspecified; if SCAN changes committed output or a dirty positive survives STOP, evidence semantics are invalid.
""")

    write(DOC / "05_MATHEMATICAL_IDENTITIES_AND_ASSUMPTIONS.md", """
# Mathematical identities and assumptions

## AUC audit

For right-continuous staircase utility, partitioning at commit times proves `integral u = u(0)T + sum Delta u_k(T-t_k)`. Here `u(0)=0`. With F1, `Delta u_k` is set-dependent; the event surrogate is not algebraically equivalent to AnytimeAUC_F1.

## SMDP recursion

`V^pi(I,rho)=E_pi[integral_0^rho u(I_z) dz]` and, for an admissible action with duration `tau_a<=rho`, `Q^pi(I,a,rho)=E[u(I)tau_a+V^pi(I',rho-tau_a)]`. Subtracting the constant current-utility area yields the incremental form `bar Q^pi=E[Delta u(I,a,I')(rho-tau_a)+bar V^pi(I',rho-tau_a)]`. Boundary convention: an action completing exactly at T is complete, but has zero remaining-horizon event surrogate; an overrun is inadmissible and never truncated into success.

## Ideal rollout claim boundary

One-step policy improvement is invoked only with an exact transition model, exact expected values, a proper pi0, inclusion of pi0's own action in the candidate set, full-horizon continuation (or exact terminal value), and zero physical planning cost. It is a method hypothesis until run. With approximate action values satisfying `||Qhat-Q||_infinity<=epsilon`, selecting the Qhat maximizer loses at most `2 epsilon` in that one decision: `Q(a*)-Q(ahat)<=2epsilon`. This is not a trajectory guarantee, finite-sample no-harm theorem, or physical no-harm result.

## Bibliographic verification

- Dimitri P. Bertsekas and John N. Tsitsiklis, *Neuro-Dynamic Programming*, Athena Scientific, Belmont, MA, 1996, ISBN 1-886529-10-8 / 978-1-886529-10-6. Metadata checked against the authors' MIT-hosted book front matter: https://web.mit.edu/dimitrib/www/NDP.pdf
- Dimitri P. Bertsekas, John N. Tsitsiklis, and Cynara Wu, “Rollout Algorithms for Combinatorial Optimization,” *Journal of Heuristics* 3(3), 245–262, 1997, DOI 10.1023/A:1009635226865. Metadata checked against the authors' paper and DBLP: https://faculty.engineering.asu.edu/bertsekas/wp-content/uploads/sites/129/2020/03/rollout.pdf and https://dblp.org/rec/journals/heuristics/BertsekasTW97

Neither citation licenses stronger claims outside its assumptions.
""")

    write(DOC / "07_DESIGN_DECISION_LEDGER.md", f"""
# Design decision ledger

| ID | Decision | Evidence / alternative | Rejection trigger |
|---|---|---|---|
| DD-01 | append-only surrogate, lambda=1 | symmetric TP/FP unit weight; sensitivities 0,2 auxiliary | revise only in a new preregistration |
| DD-02 | group FIFO confirm-as-soon-as-safe pi0 | current FIFO baseline; excludes learned scores | any hidden score/future dependency invalidates freeze |
| DD-03 | timestamp-ascending frozen scan units | simplest public deterministic iterator; unit manifest `{source_hashes['unit_manifest']}` | manifest/hash mismatch |
| DD-04 | reuse H-DS1 CONFIRM operational reserve but leave alpha unbound | separate 0.9 marginal profiles do not make their sum a complete-action 0.9 quantile | direct paired profile may bind alpha in a later freeze |
| DD-05 | block SCAN numeric binding | legacy `{legacy_scan_formula:.6f}s` is composed from per-frame p95 and post-action adaptation | unblock only with existing or newly authorized direct full-obligation calibration |
| DD-06 | exact-model, zero-noise, zero-cost H-ROLLOUT1A | discriminates mechanism existence from approximation | any estimator/planning error moves study to 1B |
| DD-07 | complete SplitMix64 seed-to-episode sampler, split distributions, and disjoint seeds frozen | prevents implementation freedom and scenario cherry-picking | fixture/hash mismatch or post-hoc edits invalidate first-look claim |
| DD-08 | named scenarios diagnostic only | protects inference from hand-case selection | inclusion in primary aggregate invalidates gate |
| DD-09 | D4 dependency-blocked | D2 executable binding required by protocol | becomes ready only after D2 re-freeze and rehash |

Strongest conclusion: the scientific design is coherent, but physical pi0 is not executable under the requested safety semantics without a full SCAN obligation profile. Main competing explanation: the legacy allowance may be conservative in practice; it still does not establish the required calibrated object. Next action is a separately authorized, bounded SCAN-profile design/run—not a toy policy comparison. Reject this block only if an authoritative existing artifact is found that directly covers the complete SCAN obligation before admission.
""")

    write(DOC / "08_SUPERSEDED_DESIGNS.md", """
# Superseded designs

- Candidate → Candidate Witness; coverage → Scan State; frontier → Event-Hypothesis Frontier; confirmed result → Committed Event.
- VERIFY-only action accounting is superseded by atomic CONFIRM accounting.
- Hard `f_min(rho)` forced-SCAN rules are superseded by a soft scarcity signal.
- Score-ranked or M0-ranked pi0 is superseded by group FIFO; M0 remains optional future estimator evidence only.
- H-PROG1 is superseded as the method direction by H-ROLLOUT1, but remains a comparison baseline.
- Asymmetric “roll out only CONFIRM” and myopic feasibility-only planning are superseded by symmetric action continuation values with net planning cost.
- Phase-quantile addition as a new safety certificate is rejected. The existing stricter H-DS1 operational CONFIRM sum is preserved in its exact scope; no analogous SCAN certificate is invented.
- Rollout v2.1/v2.2 discussion artifacts, where not present as hashable repository files, are treated as non-authoritative method hypotheses rather than silently reconstructed.
""")

    utility_hash = sha(OUT / "UTILITY_REGISTRY.json")
    base_hash = sha(OUT / "BASE_POLICY_SPEC.json")
    schema_hash = sha(OUT / "TOY_ENVIRONMENT_SCHEMA.json")
    env_hash = canonical_hash({"schema_sha256": schema_hash, "construction_sha256": construction_hash})
    dist_hash = sha(OUT / "TOY_PARAMETER_DISTRIBUTION.yaml")
    prereg = {
        "hypothesis_id": "H-ROLLOUT1A",
        "name": "Ideal Symmetric Rollout Mechanism",
        "status": "BLOCKED_DEPENDENCY_D2_NUMERIC_BINDING",
        "scientific_question": "Under an exact generative model, full-horizon rollout, zero estimator error, and ideal zero planning cost, does symmetric continuation evaluation of safe SCAN and CONFIRM actions outperform frozen shielded pi0, Ratio-PSVR, and the best fixed strategy over continuous non-extreme workload regimes?",
        "excluded_claims": ["M0 cross-source generalization", "real world-model accuracy", "Monte Carlo finite-sample error", "physical planning overhead", "real runtime throughput", "production deployment", "query-conditioned refiner", "multi-fidelity"],
        "base_policy_hash": base_hash,
        "utility_registry_hash": utility_hash,
        "toy_environment_hash": env_hash,
        "toy_environment_schema_hash": schema_hash,
        "toy_construction_hash": construction_hash,
        "named_scenario_hash": named_hash,
        "parameter_distribution_hash": dist_hash,
        "development_seed_hash": canonical_hash(dev_seeds),
        "heldout_seed_hash": canonical_hash(held_seeds),
        "methods": {
            "B0_SCAN_THEN_CONFIRM": "SCAN timestamp order while productive-safe; when no further productive-safe SCAN, group-FIFO CONFIRM to STOP",
            "B1_SHIELDED_PI0": "exact D2 policy",
            "B2_FIXED_PERIODIC": "separate frozen arms k in [1,2,4,8]: after every k safe SCANs do one group-FIFO CONFIRM if safe; otherwise continue safe SCAN; STOP fail-closed",
            "B3_CAPACITY_MATCHING": "capacity=floor(rho/R_C); SCAN while safe and frontier hypothesis count<capacity, else group-FIFO CONFIRM",
            "B4_RATIO_PSVR": "choose safe action maximizing exact-model conditional expected one-step surrogate increment divided by complete expected duration; uses visible history/posterior, never latent realization; ties pi0 then action identifier",
            "M1_IDEAL_ROLLOUT_PSVR": "full-horizon symmetric rollout defined below",
            "C0_CLAIRVOYANT_DP_CEILING": "latent-state finite-horizon DP, evaluator-only and limited to exactly enumerable episode sizes",
        },
        "simple_comparator_set": ["B0_SCAN_THEN_CONFIRM", "B2_FIXED_PERIODIC_k1", "B2_FIXED_PERIODIC_k2", "B2_FIXED_PERIODIC_k4", "B2_FIXED_PERIODIC_k8", "B3_CAPACITY_MATCHING", "B4_RATIO_PSVR"],
        "rollout": {"candidate_actions": "all safe actions including pi0 action", "first_action": "execute candidate once", "continuation": "same frozen shielded pi0 to horizon", "horizon": "full", "model": "exact", "value": "exact expectation/enumeration preferred", "mc_rule": "if MC is necessary, independent SplitMix64 streams keyed by (episode,decision,action,sample); 99% normal-CI half-width <= 1e-8*max(1,M*T) utility-seconds, cap 100000000 samples; cap failure is NUMERICAL_BLOCK and cannot be imputed", "planning_cost_seconds": 0},
        "metrics": {
            "primary": "sum over exact unique TP event ids of max(T-first_durable_commit_time,0) minus sum over unique FP ids of max(T-first_durable_commit_time,0); lambda=1; duplicate=0",
            "AnytimeAUC_F1": "(1/T)*integral_0^T F1(t)dt; F1=0 when committed set empty; otherwise exact-id precision/recall harmonic mean with precision=1 for no predictions and recall=1 for no latent events",
            "TTFC": "first durable unique-TP commit time; censored to T for aggregates and accompanied by no-commit indicator",
            "event_matching": "one-to-one exact latent_event_id; null-id commit is FP; no interval-IoU matching",
            "secondary": ["AnytimeAUC_F1", "TTFC", "TTFC_no_commit_indicator", "unique_committed_events_at_T", "event_recall_at_T", "duplicate_CONFIRM_count"],
        },
        "statistical_unit": "independent latent video episode",
        "not_independent": ["actions within episode", "multiple deadlines within episode", "rollout MC samples"],
        "aggregation": {"pairing": "same episode seed across methods", "macro": "unweighted arithmetic mean across all 512 heldout episodes", "median": "standard midpoint median of episode paired differences", "regime_cells": "3 event processes x 3 cost regimes fixed by split-index assignment; per-cell unweighted mean", "worst_regime": "minimum of the nine per-cell M1-minus-comparator means", "heatmap": "8 equal-probability bins per displayed continuous axis using frozen theoretical quantile cutpoints; show count and paired mean in every bin; no smoothing for gates"},
        "continuous_positive_neighborhood": {"family_filters": {"SPARSE": "UNIFORM_SPARSE", "BURSTY": "BURSTY_CLUSTERED", "HETEROGENEOUS_COST": "cost_variance in heldout upper half [0.4,0.8]"}, "axis": "assigned family's event-density quantile", "bins": 8, "positive_bin": "n>=12, paired mean M1-comparator > 1e-8*max(1,mean(M*T)), and median paired difference >=0", "neighborhood": ">=3 consecutive positive bins against both B1 and the best simple comparator selected globally by heldout macro", "no_pooling_or_smoothing": True},
        "gates": {
            "A_MECHANISM_EXISTENCE": ["M1 heldout macro primary > B1", "M1 heldout macro primary > B4 Ratio-PSVR", "M1 heldout macro primary > maximum heldout macro among frozen simple_comparator_set", "gain not confined to named extreme", "continuous positive neighborhoods in at least two of SPARSE/BURSTY/HETEROGENEOUS_COST"],
            "B_DENSE_HONESTY": ["include DENSE_HOMOGENEOUS", "report pi0 wins without deletion or downweighting"],
            "C_TRANSITION_VALUE": ["use frozen floor/transition/saturation rule", "test concentration of gain for floor<T<saturation"],
            "D_COMPLEXITY": ["M1 versus Ratio-PSVR", "report rollout decisions, trajectories, asymptotic complexity", "record COMPLEXITY_NOT_YET_JUSTIFIED if gain is tiny"],
        },
        "acceptance": ["macro primary > shielded pi0", "macro primary > Ratio-PSVR", "macro primary > maximum frozen simple comparator", "continuous positive area in >=2 non-extreme families", "gain includes earlier durable commits: positive paired AnytimeAUC contribution remains after conditioning on equal endpoint event count", "no future access", "no evaluator leakage", "all named adverse scenarios reported", "trace-recomputable from immutable action/transition/commit ledger", "independent review has no blocking defect"],
        "minimum_scientific_significance": ["not floating-point error", "not one discrete event jump alone", "same direction in a continuous parameter neighborhood"],
        "branches": {"ACCEPT": "ACCEPT_IDEAL_MECHANISM -> H-ROLLOUT1B_APPROXIMATION_ROBUSTNESS", "PARTIAL": "PARTIAL_EXTREME_REGIME_ONLY; no runtime", "REJECT": "retain Ratio-PSVR or pi0; do not add world-model complexity", "BLOCKED": ["environment contradiction", "D2 incomplete", "frozen environment unimplementable", "results not recomputable"]},
        "forbidden_posthoc_changes": ["utility", "lambda primary", "pi0", "gates", "environment distribution", "seed split", "regime weights", "deadline classes", "named-scenario promotion", "baseline identities", "selecting favorable scenarios"],
        "execution_authorized": False,
    }
    write_json(OUT / "H_ROLLOUT1A_PREREGISTRATION.json", prereg)

    write(DOC / "04_D4_H_ROLLOUT1A_PREREGISTRATION.md", """
# D4 — H-ROLLOUT1A preregistration

Status: `LOGICAL_PREREGISTRATION_COMPLETE`, execution status: `BLOCKED_DEPENDENCY_D2_NUMERIC_BINDING`.

The hypothesis, Ideal Symmetric Rollout Mechanism, asks whether exact full-horizon symmetric continuation evaluation improves over frozen shielded pi0, Ratio-PSVR, and the best fixed policy in continuous non-extreme regimes under exact dynamics, zero estimator noise, and zero ideal planning cost. It does not test M0 transport, a real world model, MC error, physical planning overhead/throughput, deployment, temporal refinement, or multi-fidelity.

For each safe candidate action, execute it once and then use the same pi0 to horizon. The pi0 action is always included. Exact expectation/enumeration is preferred. If MC is unavoidable, its independent stream keys, 99% absolute half-width threshold, 100-million-sample cap, and numerical-block branch are fixed in JSON and never scaled to the observed effect. Baseline action rules—including fixed periods 1/2/4/8 and the visible-posterior expected-increment/cost Ratio-PSVR—are frozen there.

The primary metric is exact-ID time-weighted unique-event utility at lambda=1; perfect Oracle makes FP zero but does not alter the registry. JSON fixes F1 empty-set behavior, normalized AUC, TTFC censoring plus indicator, exact matching, episode pairing, unweighted macro/median, nine regime cells, worst cell, heatmap bins, minimum cell size, numerical tolerance, and the three-consecutive-bin neighborhood rule. Statistical inference uses paired independent episodes, never actions, deadlines, or MC samples.

Gate A separately requires macro wins over pi0, Ratio-PSVR, and the maximum of every frozen simple arm, plus continuous positive neighborhoods in two of sparse, bursty, and heterogeneous-cost families. Gate B retains dense homogeneous evidence even if pi0 wins. Gate C uses the result-blind parameter-file rule for floor/transition/saturation, including explicit no-saturation/no-transition statuses. Gate D reports decisions, simulated trajectories, asymptotic cost, and `COMPLEXITY_NOT_YET_JUSTIFIED` when appropriate.

ACCEPT additionally requires earlier durable commits, no leakage, all named adverse scenarios, trace recomputation, and no blocking independent-review defect. A one-event jump or floating error is not scientifically meaningful without a same-direction parameter neighborhood. Partial/reject/blocked branches and all forbidden post-hoc edits are exact in the JSON.

The JSON binds exact D1/D2/D3 hashes. It must be reissued—not silently edited—after a legitimate D2 SCAN calibration. No H-ROLLOUT1A execution is authorized by this blocked preregistration.
""")

    write(OUT / "NEXT_EXACT_COMMAND.md", """
# Next exact command

`python scripts/validate_psvr_rollout_preimplementation.py`

This is the only authorized next command under the current blocked freeze. It performs static validation only. Simulator implementation and any development/held-out execution remain unauthorized until D2 has a directly calibrated complete SCAN obligation bound and D4 is re-hash-bound.
""")

    write(OUT / "FINAL_REPORT.md", f"""
# PSVR / Rollout-PSVR preimplementation final report

```text
AUTHORITY_STATE = FROZEN_RESULT_BLIND
TERMINOLOGY_FREEZE = COMPLETE
D1_UTILITY_REGISTRY = COMPLETE
D1_PRIMARY_SURROGATE = TIME_WEIGHTED_UNIQUE_EVENT_TP_MINUS_LAMBDA_FP
D1_PRIMARY_LAMBDA = 1
D1_FINAL_METRICS = ANYTIMEAUC_F1_AND_EVENT_METRICS_NOT_SURROGATE_EQUIVALENT

D2_BASE_POLICY = LOGICAL_SPEC_COMPLETE_FAIL_CLOSED
D2_DEADLINE_SAFETY_SEMANTICS = CONDITIONAL_BOUND_THEOREM_PLUS_EMPIRICAL_CHANCE_SAFETY_ONLY
D2_NUMERIC_BINDING = BLOCKED_TOTAL_SCAN_BOUND_ALPHA_SCAN_ALPHA_CONFIRM_MIN_ACTION_DURATION
D2_PROPERNESS = CONDITIONAL_PROOF_COMPLETE_NUMERIC_PREMISE_UNBOUND
D2_NON_ANTICIPATORY = COMPLETE
D2_F_MIN_ROLE = SOFT_SIGNAL_ONLY

D3_TOY_MODEL = COMPLETE_SCHEMA_AND_DETERMINISTIC_CONSTRUCTION_FROZEN
D3_PARAMETER_DISTRIBUTION = COMPLETE_FROZEN
D3_DEVELOPMENT_SEEDS = 11000..11127
D3_HELDOUT_SEEDS = 91000..91511_DISJOINT
D3_GROUPING_ERROR_MODEL = UNDER_MERGE_PLUS_IRRECOVERABLE_OVER_MERGE

D4_H_ROLLOUT1A_PREREGISTRATION = LOGIC_COMPLETE_EXECUTION_BLOCKED_BY_D2
D4_BASELINES = B0_B1_B2_B3_B4_M1_C0
D4_PRIMARY_METRIC = TIME_WEIGHTED_UNIQUE_EVENT_UTILITY_LAMBDA_1
D4_ACCEPTANCE_GATES = A_B_C_D_PLUS_NINE_ACCEPTANCE_REQUIREMENTS
D4_POSTHOC_CHANGES_FORBIDDEN = TRUE

TOY_RESULTS_GENERATED = false
PHYSICAL_CALLS_STARTED = 0
GPU_JOBS_STARTED = 0
HELD_OUT_REAL_DATA_OPENED = false

PREIMPLEMENTATION_FREEZE = BLOCKED_D2_NUMERIC_BINDING
BLOCKERS = NO_DIRECT_CALIBRATED_PREACTION_FULL_OBLIGATION_SCAN_BOUND; NO_ALPHA_SCAN; NO_DIRECT_COMPLETE_CONFIRM_CHANCE_ALPHA; NO_CERTIFIED_GLOBAL_MIN_ACTION_DURATION
NEXT_RESEARCH_STAGE = D2_FULL_SCAN_OBLIGATION_PROFILE_PREREGISTRATION_REQUIRES_SEPARATE_AUTHORIZATION
NEXT_EXACT_COMMAND = python scripts/validate_psvr_rollout_preimplementation.py
```

Strongest supported conclusion: D1 and D3 are frozen and D2/D4 logic is auditable, but the package cannot honestly claim an executable preimplementation freeze. Decisive evidence is the mismatch between required complete-action chance bindings and existing evidence: SCAN uses a legacy per-frame-p95/adaptive formula, while CONFIRM sums two marginal operational bounds without a joint alpha. Practical conservatism is the main alternative explanation; it does not establish the defined statistical objects. Unblock with direct complete-action SCAN and paired CONFIRM calibration under matching runtime identity, then re-run static validation and regenerate every dependent hash.
""")

    # Preserve a completed independent review across deterministic rebuilds.
    review_path = OUT / "INDEPENDENT_ADVERSARIAL_REVIEW.md"
    pending_review = """
# Independent adversarial review

Status: `PENDING_INDEPENDENT_REVIEW`.

The build intentionally leaves this artifact pending until a separate reviewer examines the completed D1--D4 package. The freeze cannot be reported as complete while this status remains.
"""
    if not review_path.exists() or "PENDING_INDEPENDENT_REVIEW" in review_path.read_text(encoding="utf-8"):
        write(review_path, pending_review)

    # Manifest intentionally excludes itself to avoid an impossible self-hash.
    artifacts = sorted(
        [p for p in DOC.iterdir() if p.is_file()]
        + [p for p in OUT.iterdir() if p.is_file() and p.name not in {"PREIMPLEMENTATION_FREEZE_MANIFEST.json", "PREIMPLEMENTATION_COMPLETION_AUDIT.json"}]
        + [
            ROOT / "scripts/build_psvr_preimplementation_freeze.py",
            ROOT / "scripts/validate_psvr_rollout_preimplementation.py",
            ROOT / "src/garc_eval/psvr_preimplementation.py",
            ROOT / "tests/test_psvr_preimplementation.py",
        ],
        key=lambda p: str(p.relative_to(ROOT)),
    )
    entries = []
    for path in artifacts:
        rel = str(path.relative_to(ROOT))
        review_complete = "PENDING_INDEPENDENT_REVIEW" not in review_path.read_text(encoding="utf-8")
        entries.append({"path": rel, "size": path.stat().st_size, "sha256": sha(path), "status": "FROZEN" if path.name != "INDEPENDENT_ADVERSARIAL_REVIEW.md" or review_complete else "PENDING_REVIEW", "dependencies": [], "supersedes": []})
    manifest = {
        "manifest_id": "PSVR_ROLLOUT_PREIMPLEMENTATION_FREEZE_V1",
        "generated_at": created,
        "status": "BLOCKED_D2_NUMERIC_BINDING",
        "self_hash_policy": "manifest excludes itself and completion audit to avoid circular hashes",
        "source_inputs": [{"path": str(path.relative_to(ROOT)), "sha256": source_hashes[name]} for name, path in SOURCE.items()],
        "artifacts": entries,
        "bindings": {"D1_utility_registry_sha256": utility_hash, "D2_base_policy_sha256": base_hash, "D3_toy_environment_combined_sha256": env_hash, "D3_toy_schema_sha256": schema_hash, "D3_toy_construction_sha256": construction_hash, "D3_named_scenarios_sha256": named_hash, "D3_parameter_distribution_sha256": dist_hash, "D4_preregistration_sha256": sha(OUT / "H_ROLLOUT1A_PREREGISTRATION.json")},
    }
    write_json(OUT / "PREIMPLEMENTATION_FREEZE_MANIFEST.json", manifest)

    audit = {
        "audit_id": "PSVR_PREIMPLEMENTATION_COMPLETION_AUDIT_V1",
        "status": "BLOCKED_D2_NUMERIC_BINDING",
        "checks": {
            "D1_complete": True,
            "D2_logical_spec_complete": True,
            "D2_numeric_binding_complete": False,
            "D2_numeric_binding_explicitly_blocked": True,
            "D3_schema_complete": True,
            "D3_development_heldout_seed_universes_disjoint": not set(dev_seeds) & set(held_seeds),
            "D3_parameter_distributions_separately_frozen": True,
            "D4_references_frozen_D1_D3": True,
            "D4_execution_ready": False,
            "no_toy_policy_result_exists": True,
            "no_physical_call_started_by_builder": True,
            "no_GPU_extraction_started_by_builder": True,
            "no_heldout_real_data_opened_by_builder": True,
            "all_nonself_manifest_hashes_recompute": True,
            "schema_validators_pass": None,
            "focused_tests_pass": None,
            "independent_adversarial_review_clear": None,
        },
        "blockers": list(base["blocking_fields"]),
        "completion_rule": "COMPLETE only after all checks true, D2 re-frozen, D4 rebound, and review clear",
    }
    write_json(OUT / "PREIMPLEMENTATION_COMPLETION_AUDIT.json", audit)


if __name__ == "__main__":
    main()
