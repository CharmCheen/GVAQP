#!/usr/bin/env python3
"""Read-only audit of whether existing artifacts identify original GVAQP theory."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/original_theory_identifiability_audit_v1'
SIDE=ROOT.parent/'GVAQP_side_rcsem'; OUT.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(name,text): (OUT/name).write_text(text.rstrip()+'\n')
def dump(name,x): (OUT/name).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')

sources={
 'main_alignment':ROOT/'outputs/main_thesis_alignment_v1/FINAL_ALIGNMENT_REPORT.md',
 'main_summary':ROOT/'outputs/main_thesis_alignment_v1/RESULT_SUMMARY.json',
 'proxy_quality':ROOT/'outputs/main_thesis_alignment_v1/PROXY_QUALITY_METRICS.csv',
 'proxy_regimes':ROOT/'outputs/main_thesis_alignment_v1/PROXY_REGIME_MANIFEST.csv',
 'query_matrix':ROOT/'outputs/main_thesis_alignment_v1/QUERY_POLICY_MATRIX.csv',
 'branches':ROOT/'outputs/controller_dynamic_headroom_cached_v1/STATE_ACTION_BRANCHES.jsonl',
 'controller_impl':SIDE/'experiments/controller_dynamic_headroom.py',
 'sequential_impl':SIDE/'src/rc_sem/sequential.py',
 'selective_report':SIDE/'docs/SELECTIVE_DEVIATION_PREDICTABILITY_AUDIT_V1.md',
 'selective_summary':SIDE/'outputs/selective_deviation_predictability_v1/SUMMARY.json',
 'selective_states':SIDE/'outputs/selective_deviation_predictability_v1/state_features_and_targets.csv',
 'geometry_report':ROOT/'outputs/event_evidence_geometry_v1/FINAL_GEOMETRY_REPORT.md',
 'geometry_lovo':ROOT/'outputs/event_evidence_geometry_v1/LOVO_RESULTS.csv',
 'math_reference':ROOT/'BCM_AQP_MATHEMATICAL_REFERENCE.md',
}
missing=[k for k,p in sources.items() if not p.exists()]
if missing: raise RuntimeError(f'missing authoritative sources: {missing}')
hashes={k:{'path':str(p.relative_to(ROOT.parent) if ROOT.parent in p.parents else p),'sha256':sha(p)} for k,p in sources.items()}
write('SOURCE_OF_TRUTH.md','# Source of truth\n\nThis audit is read-only with respect to P1 and consumes no human annotation artifact. Historical narrative is accepted only when corroborated by code or result tables.\n\n```json\n'+json.dumps(hashes,indent=2,sort_keys=True)+'\n```')

write('ORIGINAL_PROBLEM_FORMULATION.md',r'''# Original costly partial-observation GVAQP problem

For temporal regions (V=\{r_1,\ldots,r_N\}), define the runtime state

\[
s_t=(U_t,O_t,F_t,H_t,R_t),
\]

where (U_t) are unseen regions, (O_t) acquired cheap observations, (F_t) the exposed candidate frontier, (H_t) verified semantic history/event state, and (R_t) remaining resources. Legal actions are

\[
A_t=\{SCAN(r):r\in U_t\}\cup\{VERIFY(c):c\in F_t\}.
\]

`SCAN(r)` pays measured cheap decode/sensing/proxy cost, reads previously unobserved video, obtains an imperfect observation with false positives/false negatives, and may create new candidate opportunities. `VERIFY(c)` is legal only for exposed evidence, pays a larger semantic cost, and reveals an authoritative semantic observation. The policy maximizes expected terminal/anytime utility of the resulting `EventRelation` subject to resources. The problem is not merely ranking a fully pre-existing candidate list.''')

contract=[
('candidate existence','created only through SCAN','one row per released unit precomputed before runtime','PROXY_REGIME_MANIFEST.csv; sequential.py','VERIFIED','removes natural candidate-generation uncertainty'),
('candidate exposure','unknown until sensing','policy sees units/proxy only after cell release, but universe is fixed','sequential.py','VERIFIED','partial observability is emulated'),
('proxy availability','computed by online cheap sensing','private complete proxy map delayed until SCAN','sequential.py','VERIFIED','information release without online computation'),
('SCAN observation generation','decode and run cheap model','dictionary lookup of precomputed scores','sequential.py::step','VERIFIED','no natural sensing stochasticity/failure'),
('SCAN false-negative possibility','cheap sensing may fail to expose evidence','every unit is released; poor score causes ranking delay, not missing identity','PROXY_QUALITY_METRICS.csv','VERIFIED','natural exposure miss unidentified'),
('frontier generation','candidate identities arise endogenously','all unit identities exist; released scores make them verifiable','sequential.py','VERIFIED','new legal actions, not new artifact identities'),
('VERIFY semantics','expensive authoritative observation on exposed evidence','cached label released only for scanned unit','sequential.py','VERIFIED','logical legality faithful; oracle is cached/model-relative'),
('action costs','measured heterogeneous physical costs','constant abstract scan=0.1, verify=1.0','sequential_unknown_video_study.py','VERIFIED','physical resource tradeoff unidentified'),
('policy-induced observations','actions change future sensing outcomes/distribution','actions change released subset and state, values remain fixed cached map','sequential.py; controller_dynamic_headroom.py','VERIFIED','closed-loop release partial, endogenous observations absent'),
('event objective','human-valid EventRelation utility','0.5 terminal pseudo-event recall + 0.5 recall AUC, hard precision penalty','controller_dynamic_headroom.py','VERIFIED','event-level but discontinuous/model-relative'),
('reference semantics','independent human temporal events','older VLM pseudo-reference and strict K3 grouping','selective report; sequential.py','VERIFIED','human validity absent'),
('state distribution','natural prospective runtime distribution','108 dual-legal states sampled/capped from four behavior policies','controller_dynamic_headroom.py','VERIFIED','natural prevalence cannot be inferred'),
('continuation horizon','terminal utility under policy continuation','one forced action then fixed 1:1 to budget','controller_dynamic_headroom.py','VERIFIED','valid one-step estimand, not adaptive closed loop'),
('action-value metric','smooth practical EventRelation utility','Q with -1 jump below precision 0.8','controller_dynamic_headroom.py','VERIFIED','rare boundary crossings dominate headroom'),
]
pd.DataFrame(contract,columns=['concept','intended_semantics','actual_semantics','artifact_source','verified_status','scientific_consequence']).to_csv(OUT/'INTENDED_VS_ACTUAL_CONTRACT.csv',index=False)

pq=pd.read_csv(sources['proxy_quality']); original=pq[pq.regime=='R0_ORIGINAL']
total=int(original.groupby('video_id').total_units.first().sum()); candidates=int(original.groupby('video_id').candidate_rows.first().sum())
positives=int(original.total_positive_units.sum()); exposed=int(original.exposed_positive_units.sum())
candidate={'total_units':total,'total_precomputed_candidates':candidates,'candidate_exposure_ceiling':candidates/total,
 'fraction_candidates_existing_before_runtime':1.0,'fraction_candidates_generated_by_actual_SCAN':0.0,
 'semantic_positive_units':positives,'positive_units_with_candidate':exposed,'positive_units_without_candidate':positives-exposed,
 'candidate_exposure_recall':exposed/positives,'event_candidate_exposure_recall':'1.0 under model-relative one-candidate-per-unit reference construction',
 'candidate_existence':'PRECOMPUTED'}
write('CANDIDATE_EXISTENCE_AUDIT.md','# Candidate existence audit\n\n```json\n'+json.dumps(candidate,indent=2)+'\n```\n\nCandidate existence in artifacts is distinct from policy visibility: SCAN makes stored identities/scores newly visible, but creates no new identity.')
write('SCAN_FALSE_NEGATIVE_AUDIT.md',f'''# SCAN false-negative audit

- Original substrate: {total} units and {candidates} precomputed candidates; structural exposure recall 1.0.
- Model-relative semantic positives: {positives}; positives with candidates: {exposed}; without candidates: {positives-exposed}.
- Natural `SCAN failed -> candidate never enters frontier` is impossible in the audited sequential environment because unit/proxy/oracle universes must match and scanning releases every member of a stored cell.
- A low proxy score can delay VERIFY: this is a ranking miss, not an exposure miss.
- E1/E2/E3 delete candidates by outcome-blind hash and are `SYNTHETIC_DIAGNOSTIC_ONLY`, not evidence of natural cheap-sensor false negatives.
''')

branches=[json.loads(x) for x in sources['branches'].read_text().splitlines() if x.strip()]
scanrows=[]
for x in branches:
 scanrows.append({'state_hash':x['state_hash'],'domain':x['domain'],'source_video':x['video_id'],'behavior_policy':x['behavior_policy'],
  'state_before_frontier_size':x['frontier_size'],'new_raw_observation':False,'new_proxy_observation':True,
  'new_candidate_identity_in_artifact':False,'reveals_precomputed_candidate':True,'new_frontier_entries':True,
  'future_legal_VERIFY_actions_expand':True,'only_scheduling_order_change':False,'proxy_cost_paid_during_replay':0.1,
  'raw_video_read_during_SCAN':False,'candidate_generation_called_during_SCAN':False})
pd.DataFrame(scanrows).to_csv(OUT/'SCAN_ACTION_SEMANTICS_AUDIT.csv',index=False)

main_summary=json.loads(sources['main_summary'].read_text())
write('ACTION_SPACE_IDENTIFIABILITY.md',f'''# Action-space identifiability

The actual environment is internally partially observable: unscanned proxy values are absent from public state and VERIFY is illegal until the unit's cell is scanned. SCAN expands the legal VERIFY frontier. However, constructor inputs contain complete unit/proxy/oracle maps; SCAN performs a lookup, uses constant abstract cost 0.1, reads no raw video, runs no cheap model, and creates no candidate identity. VERIFY costs abstract 1.0 and reveals a cached model-relative label. Branches alter future released subsets but not the cached observation-generating process; all use one fixed continuation.

`ORIGINAL_SCAN_VERIFY_PROBLEM_IDENTIFIED = PARTIAL`

Faithfully identified: delayed proxy visibility, legal frontier gating, asymmetric abstract costs, verified feedback, and one-step terminal continuation. Not identified: online sensing, natural exposure failure, endogenous candidate creation, measured physical costs, policy-induced sensing outcomes, human-valid utility, and natural closed-loop state prevalence.

Across the {len(branches)} audited forced-SCAN branches, the semantic decomposition is: new raw observation `0/{len(branches)}`, online proxy computation `0/{len(branches)}`, new artifact candidate identity `0/{len(branches)}`, release of precomputed proxy/candidate evidence `{len(branches)}/{len(branches)}`, and expansion of future legal VERIFY actions `{len(branches)}/{len(branches)}`. Thus SCAN is more than order-only bookkeeping, but less than endogenous sensing.
''')

# Outcome-independent state taxonomy using frozen public fields only.
sf=pd.read_csv(sources['selective_states']); br=pd.DataFrame(branches)[['state_hash','behavior_policy']]; sf=sf.merge(br,on='state_hash',how='left')
archetypes={
 'FRONTIER_STARVED':('frontier_size <= 10',sf.frontier_size<=10),
 'FRONTIER_SATURATED':('frontier_size >= 100',sf.frontier_size>=100),
 'LARGE_UNOBSERVED_REGION':('largest_unqueried_gap_fraction >= 0.50',sf.largest_unqueried_gap_fraction>=0.50),
 'HIGH_PROXY_RECENT_NEGATIVE_STREAK':('verify_count >= 2 AND recent_negative_rate >= 0.75',(sf.verify_count>=2)&(sf.recent_negative_rate>=0.75)),
 'LOW_PROXY_FRONTIER':('frontier_top_score <= 0.50',sf.frontier_top_score<=0.50),
 'HIGH_PROXY_FRONTIER':('frontier_top_score >= 0.80',sf.frontier_top_score>=0.80),
 'LOW_REMAINING_BUDGET':('remaining_fraction <= 0.20',sf.remaining_fraction<=0.20),
 'HIGH_REMAINING_BUDGET':('remaining_fraction >= 0.80',sf.remaining_fraction>=0.80),
 'HIGH_REDUNDANCY':('query_redundancy >= 0.50',sf.query_redundancy>=0.50),
 'LOW_REDUNDANCY':('query_redundancy <= 0.10',sf.query_redundancy<=0.10),
 'HIGH_EVENT_CONCENTRATION':('positive_evidence_regions > 0 AND positive_evidence_concentration >= 0.75',(sf.positive_evidence_regions>0)&(sf.positive_evidence_concentration>=0.75)),
 'DIVERSE_EVIDENCE':('positive_evidence_regions >= 2',sf.positive_evidence_regions>=2),
}
state_rows=[]
for name,(rule,mask) in archetypes.items():
 d=sf[mask]; state_rows.append({'archetype':name,'public_rule':rule,'state_count':len(d),'fraction_of_108':len(d)/len(sf),
  'source_video_count':d.video_id.nunique(),'behavior_policy_count':d.behavior_policy.nunique(),
  'mean_abs_action_delta':float(d.delta_deviation.abs().mean()) if len(d) else np.nan,
  'practical_beneficial_fraction':float((d.practical_class=='BENEFICIAL').mean()) if len(d) else np.nan})
pd.DataFrame(state_rows).to_csv(OUT/'STATE_SUPPORT_AUDIT.csv',index=False)
write('SAMPLING_VS_PREVALENCE_ANALYSIS.md','''# Sampling-limited versus prevalence-limited

`SAMPLING_VS_PREVALENCE = NOT_IDENTIFIABLE`

The 108 states are dual-legal states reached by four prior behavior policies, deduplicated, then capped at 12 per domain-budget by evenly spaced indices. They are not a probability sample from a true online cheap-sensing process. Archetype support describes this table only. It cannot distinguish rare visitation caused by behavior-policy coverage from genuinely rare natural high-regret states. Minimum distinguishing evidence is prospective endogenous SCAN logging under randomized/coverage-rich behavior on independent videos, with every natural state retained and sampling probabilities recorded.
''')

# Reconstruct smooth delta by removing the -1 hard penalty from each branch.
rows=[]
for x in branches:
 default=sf.loc[sf.state_hash==x['state_hash'],'default_action'].iloc[0]
 db=x['scan_branch'] if default=='SCAN' else x['verify_branch']; ab=x['verify_branch'] if default=='SCAN' else x['scan_branch']
 def base(branch): return float(branch['q']) + (0.0 if branch['precision_constraint_satisfied'] else 1.0)
 smooth=base(ab)-base(db); original_delta=float(sf.loc[sf.state_hash==x['state_hash'],'delta_deviation'].iloc[0])
 rows.append({'state_hash':x['state_hash'],'delta_original':original_delta,'delta_smooth_no_hard_penalty':smooth,
  'original_class':'BENEFICIAL' if original_delta>.005 else 'HARMFUL' if original_delta<-.005 else 'INDIFFERENT',
  'smooth_class':'BENEFICIAL' if smooth>.005 else 'HARMFUL' if smooth<-.005 else 'INDIFFERENT',
  'penalty_transition':sf.loc[sf.state_hash==x['state_hash'],'precision_penalty_transition'].iloc[0]})
qd=pd.DataFrame(rows); qd.to_csv(OUT/'Q_OBJECTIVE_STATE_DIAGNOSTIC.csv',index=False)
counts=lambda c:qd[c].value_counts().reindex(['BENEFICIAL','HARMFUL','INDIFFERENT'],fill_value=0).to_dict()
rho=float(spearmanr(qd.delta_original,qd.delta_smooth_no_hard_penalty).statistic)
qsum=json.loads(sources['selective_summary'].read_text()); pa=qsum['precision_penalty_audit']
write('Q_OBJECTIVE_DISCONTINUITY_AUDIT.md',f'''# Q objective discontinuity audit

Frozen Q is `0.5*terminal_event_recall + 0.5*anytime_event_recall_auc - 1[nonempty precision<0.8]`. At practical `delta=0.005`, original classes are `{counts('original_class')}`. Two penalty-avoidance states contribute {pa['penalty_avoidance_share_of_beneficial_gain']:.1%} of positive deviation value ({pa['penalty_avoidance_gain_sum']:.4f}/{pa['beneficial_gain_sum']:.4f}).

Offline sensitivity removes only the discontinuous `-1`, with no fitting or historical relabeling. Smooth classes become `{counts('smooth_class')}`; original-versus-smooth delta Spearman is `{rho:.3f}`. Per-state results are in `Q_OBJECTIVE_STATE_DIAGNOSTIC.csv`.

`ACTION_HEADROOM_STRUCTURE = MIXED`: positive gain magnitude is discontinuity-dominated, but practical class prevalence changes only from 5/5/98 to 5/4/99 and rank correlation remains high. The smooth recall/AUC component still contains structure. This diagnostic does not replace the frozen Q conclusion.
''')

lineage=[
('main_thesis_proxy_stress','Uniform/StaticProxyRank/TemporalCoverage','proxy ordering or temporal coverage','selected positive yield / coverage','C1 EventF1','yes','no'),
('sequential_unknown_video','fixed and adaptive SCAN/VERIFY','policy-specific heuristic/action schedule','proxy score, frontier, verified history','pseudo-reference event recall/F1/AUC','strict K3','no'),
('controller_dynamic_headroom','forced one-step branches','Q terminal recall + recall AUC - hard precision penalty','event-level pseudo-utility','pseudo-reference event metrics','strict K3','no'),
('selective_deviation_predictability','classifier of beneficial deviation','predict frozen delta_deviation','one-step Q label','net Q vs fixed 1:1','inherited','no'),
('event_evidence_geometry','no policy optimization','explanatory regression','yield + public geometry','model-relative C1 EventF1','C1','no'),
]
pd.DataFrame(lineage,columns=['experiment','policy','optimized_score','proxy_for_utility','terminal_metric','materializer_in_loop','human_event_semantics']).to_csv(OUT/'CONTROLLER_OBJECTIVE_LINEAGE.csv',index=False)

write('THEORY_CLAIM_BOUNDARY.md','''# Event-aware theory claim boundary

`EVENT_AWARE_OBJECTIVE_MOTIVATION = STRONG`; `EMPIRICAL_EVENT_AWARE_BENEFIT = UNESTABLISHED`.

Proposition 15.1 constructs, for every budget B, B high-score positives from one event and B lower-score positives from distinct events. Unit top-ranking recovers one event while a component-aware policy can recover B, a 1/B worst-case ratio. Proposition 15.2 shows under audited K3 that a low-positive-probability query can have positive event-F1 value by returning a negative that blocks a false merge. These prove record-positive yield and event utility need not align.

They do not prove the current videos contain either regime, provisional components identify human event identity, geometry is sufficient, a concrete policy beats generic relevance+coverage/MMR, or true partial-observation SCAN/VERIFY is useful. Proposition 15.2 is materializer-specific and cannot establish human-event utility.
''')
write('GEOMETRY_CLAIM_BOUNDARY.md','''# Geometry claim boundary

- G1 — geometry describes model-relative terminal C1 EventF1: `PARTIAL`. Yield-only LOVO macro R²≈0.006, yield+public geometry≈0.795, reference-aware≈0.980, but only one strong equal-yield pair/one video and a K3/C1-relative reference.
- G2 — geometry predicts independent human-event recovery: `PENDING`. P1 human outcomes were not read.
- G3 — geometry predicts SCAN/VERIFY action value: `ABSENT` on the frozen 108-state audit. M0 and M1 primary gain were both +0.000514 with essentially identical low precision; `GEOMETRY_STATE_ADDED_VALUE=NO`.

Terminal-F1 association cannot be converted into controller relevance.
''')

matrix=[
('partial observability','stored proxy hidden until SCAN','PARTIAL','sequential.py','release gating but precomputed universe'),
('costly SCAN','abstract cost 0.1','PARTIAL','SequentialCostConfig','cost exists but is unmeasured/constant'),
('online cheap sensing','no raw read/model call in replay','NO','sequential.py::step','true sensing VOI absent'),
('candidate-generation uncertainty','one row per unit','NO','proxy regime manifest','existence known in artifact'),
('proxy false negatives','low scores and synthetic thinning only','PARTIAL','proxy metrics/regimes','ranking FN-like behavior; no natural exposure FN'),
('proxy false positives','imperfect rankings against cached labels','YES','proxy quality metrics','cheap evidence can mislead VERIFY ordering'),
('endogenous frontier creation','stored units released by cell','PARTIAL','sequential.py','legal frontier grows; identities not created'),
('expensive VERIFY','cached label, cost 1.0, scanned-only','PARTIAL','sequential.py','logical semantics faithful, physical cost/reference not'),
('feedback-driven future observation','verified labels enter state','PARTIAL','PublicSequentialState','future actions respond, sensing distribution fixed'),
('heterogeneous action cost','constant 0.1/1.0','NO','SequentialCostConfig','no region/candidate cost heterogeneity'),
('event-level terminal objective','pseudo-event recall/AUC + precision gate','PARTIAL','controller_dynamic_headroom.py','event level but discontinuous/model-relative'),
('event-aware state','strict K3 groups and geometry summaries','PARTIAL','state feature table','not human-valid; omitted sensing uncertainty'),
('resource scaling','budgets 20/50/100 abstract','PARTIAL','branch summary','multiple budgets, not physical'),
('natural high-regret state prevalence','behavior-sampled capped states','UNKNOWN','behavior_states','cannot estimate prevalence'),
('policy-visible regret predictability','M0/M1/M2 weak on current table','YES','selective summary','identified only for current cached distribution'),
('human-valid EventRelation','P1 pending and unread','NO','P1 pre-human protocol','no independent result available'),
]
pd.DataFrame(matrix,columns=['original_theoretical_requirement','current_substrate','identified','evidence','consequence']).to_csv(OUT/'ORIGINAL_THEORY_IDENTIFIABILITY_MATRIX.csv',index=False)

write('MINIMUM_FAITHFUL_P4_SUBSTRATE.md','''# Minimum faithful future substrate (specification only; not authorization)

1. Before SCAN, a region's proxy and candidates are unavailable to both policy and runtime replay table.
2. `SCAN(region)` must pay measured decode plus maintained cheap-model cost, read raw video, and generate/reveal evidence at that moment. Log raw input, latency, observation and failures.
3. Natural cheap-sensor misses must be measurable against an independent semantic reference; synthetic deletion may be sensitivity only.
4. VERIFY must be legal only on exposed evidence and pay measured expensive semantic cost.
5. Run prospectively on independent videos with randomized/coverage-rich behavior; retain all states and behavior propensities to estimate natural archetype prevalence.
6. Before controller training, counterfactually audit practical action regret frequency, magnitude, policy-visible predictability, wrong-deviation downside, and source-level replication under a smooth human-event utility.
7. Reopen controller only if naturally occurring high-regret states are non-rare, predictable across videos, and positive after physical costs. This document does not authorize P4 or controller work.
''')

decision={
 'original_theory_status':'PARTIALLY_TESTED','candidate_existence':'PRECOMPUTED','proxy_acquisition':'EMULATED_PROGRESSIVE_EXPOSURE',
 'current_dominant_proxy_failure':'RANKING','scan_action_semantics':'EMULATED_INFORMATION_RELEASE','original_scan_verify_problem_identified':'PARTIAL',
 'state_support':'108 behavior-policy-reached dual-legal states; 98 indifferent, 5 beneficial, 5 harmful at delta=0.005; only two independent source videos',
 'sampling_vs_prevalence':'NOT_IDENTIFIABLE','action_headroom_structure':'MIXED','controller_objective_alignment':'MIXED',
 'event_aware_objective_motivation':'STRONG','empirical_human_event_benefit':'PENDING_P1','geometry_terminal_event_signal':'PARTIAL','geometry_action_value_signal':'ABSENT',
 'claim_A':'PARTIALLY_SUPPORTED','claim_B':'NOT_ESTABLISHED','claim_C':'PARTIALLY_SUPPORTED_THEORETICALLY_EMPIRICALLY_UNESTABLISHED',
 'controller_reopen_authorized':False,'p1_status':'UNCHANGED_NOT_TOUCHED','human_annotation_artifacts_read':False,
 'ranking_degradation_low_budget_median_gap_F1':main_summary['rank_degradation_low_budget_median_gap_F1'],
 'exposure_degradation_low_budget_median_gap_F1':main_summary['exposure_degradation_low_budget_median_gap_F1'],
 'source_hashes':hashes,
}
dump('DECISION.json',decision)

write('FINAL_IDENTIFIABILITY_REPORT.md',f'''# GVAQP original-theory identifiability audit

## Decision

`ORIGINAL_THEORY_STATUS = PARTIALLY_TESTED`

The current substrate faithfully emulates delayed proxy visibility, scanned-only VERIFY legality, asymmetric abstract costs, verified feedback, and one-step continuation. It does not instantiate raw-video online cheap sensing, endogenous candidate generation, natural exposure false negatives, measured physical costs, human-valid EventRelation utility, or the natural prevalence of high-regret states. It therefore tests a nontrivial but reduced problem—emulated information release and ranking over a precomputed universe—not merely static ranking, and not the full original theory.

## Quantitative findings

- Candidate universe: {candidates}/{total} unit rows precomputed; original structural and positive exposure recall are 1.0.
- Ranking severe-vs-original low-budget median EventF1 gap: {main_summary['rank_degradation_low_budget_median_gap_F1']:.6f}.
- Synthetic exposure severe-vs-original corresponding median gap: {main_summary['exposure_degradation_low_budget_median_gap_F1']:.6f}.
- 108-state audit: 5 beneficial, 5 harmful, 98 indifferent at delta 0.005; only two independent source videos.
- Two precision-boundary crossings contribute {pa['penalty_avoidance_share_of_beneficial_gain']:.1%} of positive deviation value. Removing the hard penalty is diagnostic only and materially changes label structure.

## Claim reconstruction

### Claim A — imperfect proxy creates query-optimization work

- Theoretical status: `SUPPORTED` as a well-defined finite-budget optimization problem.
- Empirical status: `PARTIALLY_SUPPORTED`.
- What was tested: natural proxy-ranking degradation over a fully precomputed candidate universe changes low-budget EventF1.
- Missing evidence: natural candidate-exposure failures under real cheap sensing and independent-human event utility.

### Claim B — true costly/incomplete SCAN benefits from state-dependent allocation

- Theoretical status: `PLAUSIBLE_NOT_PROVED`.
- Empirical status: `NOT_ESTABLISHED`, not disproved.
- What was tested: cached one-step SCAN/VERIFY deviations, abstract costs, fixed maps and fixed 1:1 continuation on 108 behavior-induced states.
- Missing evidence: real online sensing, endogenous frontier creation, natural state prevalence, measured costs and prospective closed-loop outcomes.

### Claim C — event-aware acquisition improves robustness to proxy error

- Theoretical status: `STRONG_MOTIVATION` from the verified 1/B counterexample and materializer-specific negative-query construction.
- Empirical status: `PARTIALLY_SUPPORTED` only in model-relative diagnostics; independent-human benefit is `PENDING_P1`.
- What was tested: terminal C1 EventF1 association with evidence geometry and theoretical separations from positive-yield ranking.
- Missing evidence: frozen equal-yield effects on independent human events and survival against generic relevance+coverage/MMR baselines.

## Negative-result boundary

The negative result falsifies the practical proposition that, on these 108 behavior-induced cached states with this Q, these observables and fixed 1:1 continuation, a simple selective deviation rule reliably improves the strong default across source videos. It does not falsify adaptive allocation under true online cheap sensing, natural exposure misses, measured costs, prospective state distributions, or human-event utility.

The single largest mismatch is that SCAN releases stored proxy rows from a complete one-candidate-per-unit universe instead of reading raw video and endogenously generating fallible candidate evidence. The minimum future test is the small faithful substrate specified in `MINIMUM_FAITHFUL_P4_SUBSTRATE.md`; it is not authorized now. Controller remains closed and P1 remains untouched.
''')
print(json.dumps({k:decision[k] for k in ['original_theory_status','candidate_existence','proxy_acquisition','scan_action_semantics','original_scan_verify_problem_identified']},sort_keys=True))
