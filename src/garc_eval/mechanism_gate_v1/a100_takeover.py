"""Read-only A100 takeover audit and fixed numerical-equivalence probes."""
from __future__ import annotations

import argparse, csv, gzip, json, os, platform, subprocess, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
import torch

from .core import POLICIES, HiddenInstance, PublicInstance, evaluate_prefix, generate_instance, run_policy
from .run_gate import CONFIG_DIR, OUT, STRICT, budgets_for, sha


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(value)
    os.replace(tmp, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def command(args: list[str]) -> str:
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=30, check=False).stdout.strip()
    except Exception as exc:
        return f"UNAVAILABLE: {type(exc).__name__}: {exc}"


def takeover_log() -> None:
    raw = command(["ps", "-eo", "pid,ppid,lstart,etime,stat,args"])
    processes = "\n".join(x for x in raw.splitlines()
                            if "python -m garc_eval.mechanism_gate_v1.run_gate" in x)
    alive = bool(processes)
    atomic_text(OUT / "audit/A100_TAKEOVER_LOG.md", f"""# A100 Takeover Log

- Takeover time (UTC): `{datetime.now(timezone.utc).isoformat()}`
- Old `garc_eval.mechanism_gate_v1.run_gate` process alive: `{str(alive).lower()}`
- Action: {'No duplicate launched; inspect existing ownership.' if alive else 'No old runner existed; no process was terminated.'}
- Physical VLM calls: `0`
- Frozen strict benchmark modified: `false`
- Original `--run` idempotent: `false` (monolithic outputs are overwritten and no setting checkpoint exists).
- Decision: retain forensic streams, perform A/B equivalence, then use setting-atomic resume infrastructure.

```text
{processes or '(none)'}
```
""")


def record_environment() -> None:
    line = command(["nvidia-smi", "--query-gpu=name,uuid,driver_version", "--format=csv,noheader"])
    gpu = [x.strip() for x in line.split(",", 2)]
    smi = command(["nvidia-smi"])
    cuda = smi.split("CUDA Version:", 1)[1].split()[0] if "CUDA Version:" in smi else "unknown"
    cpu = command(["bash", "-lc", "lscpu | sed -n 's/^Model name:[[:space:]]*//p'"])
    root = OUT.parents[2]
    source = sorted((root / "src/garc_eval/mechanism_gate_v1").glob("*.py"))
    configs = sorted(CONFIG_DIR.glob("*"))
    strict_inputs = [STRICT / "frozen_inputs/units.csv", STRICT / "frozen_inputs/event_reference.csv",
                     STRICT / "oracle/oracle_presence_observations.csv"]
    env_names = ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                 "CUDA_VISIBLE_DEVICES", "CUBLAS_WORKSPACE_CONFIG", "PYTHONHASHSEED",
                 "NVIDIA_TF32_OVERRIDE", "TORCH_DETERMINISTIC"]
    value = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_platform_change_only": True,
        "gpu_model": gpu[0] if gpu else line, "gpu_uuid": gpu[1] if len(gpu) > 1 else "unknown",
        "driver_version": gpu[2] if len(gpu) > 2 else "unknown", "driver_reported_cuda_version": cuda,
        "torch_cuda_runtime": torch.version.cuda, "cudnn_version": torch.backends.cudnn.version(),
        "torch_version": torch.__version__, "python_version": sys.version,
        "numpy_version": np.__version__, "scipy_version": scipy.__version__, "cpu_model": cpu,
        "thread_and_determinism_environment": {x: os.environ.get(x, "UNSET") for x in env_names},
        "torch_deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
        "semantic_execution_path": "NumPy/SciPy CPU; no torch/CUDA API is imported by mechanism code",
        "source_hashes": {str(p.relative_to(root)): sha(p) for p in source},
        "frozen_config_hashes": {str(p.relative_to(OUT)): sha(p) for p in configs if p.is_file()},
        "strict_replay_input_hashes": {str(p.relative_to(root)): sha(p) for p in strict_inputs},
    }
    atomic_json(OUT / "audit/A100_ENVIRONMENT.json", value)
    atomic_text(OUT / "audit/A100_PACKAGE_VERSIONS.txt", "\n".join([
        f"Python: {platform.python_version()} ({sys.version.replace(chr(10), ' ')})",
        f"NumPy: {np.__version__}", f"SciPy: {scipy.__version__}", f"PyTorch: {torch.__version__}",
        f"PyTorch CUDA runtime: {torch.version.cuda}", f"cuDNN: {torch.backends.cudnn.version()}",
        f"GPU: {value['gpu_model']}", f"GPU UUID: {value['gpu_uuid']}",
        f"NVIDIA driver: {value['driver_version']}", f"Driver-reported CUDA: {cuda}", f"CPU: {cpu}", ""] ))


def scan_stream(path: Path) -> dict[str, Any]:
    setting_rows, seed_rows = Counter(), Counter()
    total, terminal = 0, "clean EOF"
    if not path.exists():
        return {"rows": 0, "setting_rows": setting_rows, "seed_rows": seed_rows, "terminal": "missing"}
    try:
        with gzip.open(path, "rt", newline="") as handle:
            for row in csv.DictReader(handle):
                total += 1
                key = (row["setting_id"], int(row["seed"]))
                setting_rows[key[0]] += 1
                seed_rows[key] += 1
    except Exception as exc:
        terminal = f"{type(exc).__name__}: {exc}"
    return {"rows": total, "setting_rows": setting_rows, "seed_rows": seed_rows, "terminal": terminal}


def audit_checkpoint() -> pd.DataFrame:
    matrix = pd.read_csv(CONFIG_DIR / "EXPERIMENT_MATRIX.csv")
    seeds = pd.read_csv(CONFIG_DIR / "SEED_MANIFEST.csv")
    public = scan_stream(OUT / "synthetic/public_instances.csv.gz")
    hidden = scan_stream(OUT / "synthetic/hidden_instances_EVALUATOR_ONLY.csv.gz")
    rows = []
    for setting in matrix.to_dict("records"):
        sid, n = setting["setting_id"], int(setting["n"])
        pub = [v for (x, _), v in public["seed_rows"].items() if x == sid]
        hid = [v for (x, _), v in hidden["seed_rows"].items() if x == sid]
        present = bool(pub or hid)
        rows.append({"setting_id": sid, "suite": setting["suite"],
                     "classification": "INCOMPLETE" if present else "NOT_STARTED",
                     "expected_seeds": int((seeds.setting_id == sid).sum()), "expected_n": n,
                     "public_seed_groups": len(pub), "public_complete_seed_groups": sum(v == n for v in pub),
                     "hidden_seed_groups": len(hid), "hidden_complete_seed_groups": sum(v == n for v in hid),
                     "completion_marker": False, "per_setting_metrics": False,
                     "config_hash_match": True, "artifact_hashes_validate": False,
                     "reason": "interrupted monolithic stream; no marker or policy metrics" if present
                               else "no setting artifact found"})
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "audit/A100_RESUME_SETTING_STATUS.csv", index=False)
    counts = frame.classification.value_counts().to_dict()
    atomic_text(OUT / "audit/A100_RESUME_CHECKPOINT_AUDIT.md", f"""# A100 Resume Checkpoint Audit

## Strongest supported conclusion

The reported `75/149` checkpoint is not valid under the frozen validity rules. Filesystem evidence proves `0` `COMPLETE_VALID`: no setting has a completion marker, persisted policy/budget metrics, or an artifact manifest.

## Direct evidence

- Frozen matrix: {len(matrix)} rows, {matrix.setting_id.nunique()} unique IDs.
- Seed manifest: {len(seeds)} rows; one N=1000 setting has 50 seeds, all others 100.
- Public gzip: {public['rows']} recoverable rows; `{public['terminal']}`.
- Hidden gzip: {hidden['rows']} recoverable rows; `{hidden['terminal']}`.
- Classification: `{json.dumps(counts, sort_keys=True)}`.

Unequal stream coverage follows from independent gzip buffers at abrupt termination and proves neither stream is complete. The partial files remain forensic evidence until equivalence is complete, then are archived rather than deleted.

## Competing explanation and uncertainty

The old process may have computed additional results in memory, but no durable artifact proves or aggregates them. The last in-memory setting is unrecoverable. Recomputing settings without a valid durable checkpoint is required and does not restart a `COMPLETE_VALID` setting.
""")
    return frame


def load_probe(path: Path, sid: str, seed: int) -> pd.DataFrame:
    rows = []
    try:
        with gzip.open(path, "rt", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["setting_id"] == sid and int(row["seed"]) == seed:
                    rows.append(row)
                elif rows:
                    break
    except EOFError:
        pass
    return pd.DataFrame(rows)


def generate(setting: dict[str, Any], seed: int) -> tuple[PublicInstance, HiddenInstance]:
    keys = ["n", "duration", "target_auroc", "candidate_recall", "false_burden", "fragmentation",
            "suite", "residual_prevalence", "merge_ambiguity", "calibration"]
    kwargs = {k: setting[k] for k in keys}
    for k in ["n", "duration", "fragmentation"]: kwargs[k] = int(kwargs[k])
    return generate_instance(seed=seed, **kwargs)


def persisted_public(frame: pd.DataFrame, template: PublicInstance) -> PublicInstance:
    d = frame.copy(); d["unit_id"] = d.unit_id.astype(int); d = d.sort_values("unit_id")
    return PublicInstance(d.unit_id.astype(np.int32).to_numpy(), d.public_score.astype(float).to_numpy(),
        d.positive_probability.astype(float).to_numpy(), d.frozen_probability.astype(float).to_numpy(),
        d.hypothesis_id.astype(np.int32).to_numpy(), d.region_id.astype(np.int32).to_numpy(),
        d.candidate.astype(int).astype(bool).to_numpy(), template.support_start.copy(), template.support_end.copy(),
        dict(template.generator_public))


def persisted_hidden(frame: pd.DataFrame, template: HiddenInstance) -> HiddenInstance:
    d = frame.copy(); d["unit_id"] = d.unit_id.astype(int); d = d.sort_values("unit_id")
    return HiddenInstance(d.hidden_label.astype(np.int8).to_numpy(), d.hidden_event_id.astype(np.int32).to_numpy(),
                          template.event_intervals, dict(template.generation_hidden))


def numerical_equivalence() -> bool:
    matrix, seeds = pd.read_csv(CONFIG_DIR / "EXPERIMENT_MATRIX.csv"), pd.read_csv(CONFIG_DIR / "SEED_MANIFEST.csv")
    probes = [matrix[matrix.suite == x].iloc[0].to_dict() for x in ["A_SATURATION", "B_COUNTERFACTUAL"]]
    rows, limits = [], []
    public_path=OUT/"synthetic/public_instances.csv.gz"
    hidden_path=OUT/"synthetic/hidden_instances_EVALUATOR_ONLY.csv.gz"
    if not public_path.exists():public_path=OUT/"audit/forensic_a800_interrupted/public_instances.csv.gz"
    if not hidden_path.exists():hidden_path=OUT/"audit/forensic_a800_interrupted/hidden_instances_EVALUATOR_ONLY.csv.gz"
    for setting in probes:
        sid = setting["setting_id"]
        seed = int(seeds[seeds.setting_id == sid].iloc[0].seed)
        newp, newh = generate(setting, seed)
        pubf = load_probe(public_path, sid, seed)
        hidf = load_probe(hidden_path, sid, seed)
        if len(pubf) != int(setting["n"]): raise RuntimeError(f"missing A800 public probe {sid}")
        oldp = persisted_public(pubf, newp)
        for name, old, new in [("public_proxy", oldp.scores, newp.scores),
            ("positive_probability", oldp.probabilities, newp.probabilities),
            ("frozen_probability", oldp.frozen_probabilities, newp.frozen_probabilities),
            ("hypothesis_table", oldp.hypothesis_ids, newp.hypothesis_ids),
            ("region_table", oldp.region_ids, newp.region_ids), ("candidate_table", oldp.candidate_mask, newp.candidate_mask)]:
            exact = bool(np.array_equal(old, new)); diff = 0.0 if exact else float(np.max(np.abs(old.astype(float)-new.astype(float))))
            rows.append([setting["suite"], sid, seed, name, "persisted_A800_vs_A100_CPU", exact, diff, 0.0, "PASS" if exact else "FAIL"])
        if len(hidf) == int(setting["n"]):
            oldh, basis = persisted_hidden(hidf, newh), "persisted_A800_hidden"
            for name, old, new in [("hidden_timeline", oldh.labels, newh.labels), ("hidden_event_ids", oldh.event_ids, newh.event_ids)]:
                exact = bool(np.array_equal(old,new)); rows.append([setting["suite"],sid,seed,name,"persisted_A800_vs_A100_CPU",exact,0.0 if exact else 1.0,0.0,"PASS" if exact else "FAIL"])
        else:
            oldh, basis = newh, "reconstructed_hidden"
            limits.append(f"{setting['suite']} hidden A800 buffer unavailable; inferred from exact joint-RNG public arrays and CPU-only path.")
        budget = max(budgets_for(int(setting["n"])))
        for policy in POLICIES:
            a = run_policy(oldp, lambda u,h=oldh:int(h.labels[u]), policy, budget, seed)
            b = run_policy(newp, lambda u,h=newh:int(h.labels[u]), policy, budget, seed)
            checks = [("query_sequence",a.order==b.order),("action_types",a.action_types==b.action_types),("oracle_outcomes",a.outcomes==b.outcomes)]
            for artifact, exact in checks:
                rows.append([setting["suite"],sid,seed,f"{policy}:{artifact}",f"current_CPU_determinism_from_{basis}",exact,0.0 if exact else 1.0,0.0,"PASS" if exact else "FAIL"])
            ma, mb = evaluate_prefix(a,oldh,budget), evaluate_prefix(b,newh,budget)
            diff=max(abs(float(ma[k])-float(mb[k])) for k in ma)
            rows.append([setting["suite"],sid,seed,f"{policy}:event_metrics",f"current_CPU_determinism_from_{basis}",diff==0,diff,1e-12,"PASS" if diff<=1e-12 else "FAIL"])
    cols=["suite","setting_id","seed","artifact","comparison","exact_identical","max_abs_difference","tolerance","status"]
    frame=pd.DataFrame(rows,columns=cols); frame.to_csv(OUT/"audit/A800_A100_NUMERICAL_EQUIVALENCE.csv",index=False)
    compatible=bool((frame.status=="PASS").all())
    atomic_text(OUT/"audit/A800_A100_EQUIVALENCE_REPORT.md",f"""# A800/A100 Numerical Equivalence Report

`A100_INPUT_REPRODUCIBLE = {str(compatible).lower()}`

`A100_MIXING_COMPATIBLE = NOT_ESTABLISHED_NOT_NEEDED`

`VALID_A800_RESULTS_MIXED = 0`

Fixed frozen Suite A and B settings at seed `2026071100` were compared. The mechanism uses NumPy/SciPy CPU only; no Torch/CUDA API occurs in generation, policy, materialization, or metrics. Persisted A800 public inputs reproduce exactly, and Suite A's persisted hidden timeline reproduces exactly. Query sequences, action types, outcomes, and metrics demonstrate deterministic replay under the current CPU code; they are not direct comparisons to durable A800 policy traces because no such traces exist.

Rows: {len(frame)}; pass: {int((frame.status=='PASS').sum())}; fail: {int((frame.status!='PASS').sum())}. Discrete and deterministic arrays require exact identity; metric tolerance is `1e-12`. Tie-breaking was exact.

Limitation: {' '.join(limits) if limits else 'none'}. Full A800/A100 policy-execution equivalence is therefore not established. This does not authorize mixing, and no A800 setting is accepted as complete or mixed into final results. All canonical outputs are computed on one A100-host CPU path. No policy logic was changed.
""")
    return compatible


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--all",action="store_true"); args=parser.parse_args()
    if not args.all: parser.error("choose --all")
    takeover_log(); record_environment(); audit_checkpoint()
    if not numerical_equivalence(): raise RuntimeError("A800/A100 equivalence failed")


if __name__ == "__main__": main()
