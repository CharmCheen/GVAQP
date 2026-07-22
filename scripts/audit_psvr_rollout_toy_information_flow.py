#!/usr/bin/env python3
"""Static information-flow and guarded-CLI audit; executes no policy runner."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/garc_eval/psvr_rollout_toy"
OUT = ROOT / "outputs/psvr_rollout_preimplementation"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attributes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.add(node.module or "")
    return values


def runner_help_without_main(path: Path) -> str:
    spec = importlib.util.spec_from_file_location("_heldout_runner_static_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load heldout parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parser().format_help()


def main() -> None:
    policies = SRC / "policies.py"
    schema = SRC / "schema.py"
    environment = SRC / "environment.py"
    conditional = SRC / "conditional.py"
    runner = ROOT / "scripts/run_psvr_rollout_h1a_heldout.py"
    next_command = OUT / "NEXT_HELDOUT_COMMAND.md"

    policy_attrs = attributes(policies)
    policy_imports = imports(policies)
    forbidden_attrs = {
        "episode", "events", "witnesses", "seed", "latent_event_id",
        "future_cost_draws", "future_oracle_draws", "cost_realizations",
    }
    forbidden_import_fragments = {"environment", "events", "witnesses", "evaluator"}
    direct_attr_hits = sorted(policy_attrs & forbidden_attrs)
    direct_import_hits = sorted(
        value for value in policy_imports
        if any(fragment in value for fragment in forbidden_import_fragments)
    )

    schema_text = schema.read_text(encoding="utf-8")
    environment_text = environment.read_text(encoding="utf-8")
    conditional_text = conditional.read_text(encoding="utf-8")
    help_text = runner_help_without_main(runner)
    command_text = next_command.read_text(encoding="utf-8")
    cli_flags = ["--preregistration", "--confirm-heldout"]
    cli_match = all(flag in help_text and flag in command_text for flag in cli_flags)
    output_dir = OUT / "h_rollout1a_heldout"

    checks = {
        "ordinary_policy_has_no_forbidden_attribute_access": not direct_attr_hits,
        "ordinary_policy_has_no_latent_environment_import": not direct_import_hits,
        "visible_state_contains_episode_id": "episode_id: str" in schema_text,
        "episode_id_literal_contains_seed": 'f"{split}_{seed}"' in environment_text,
        "conditional_evaluator_rejects_declared_realized_access": "sampler.realized_episode_access" in conditional_text,
        "conditional_evaluator_requires_visible_state_match": "world.visible_state() != visible_state" in conditional_text,
        "heldout_cli_matches_prepared_command": cli_match,
        "heldout_main_called_by_this_audit": False,
        "heldout_seed_file_opened_by_this_audit": False,
        "heldout_output_empty": not output_dir.exists() or not any(output_dir.iterdir()),
    }
    status = "FAIL_BLOCKING_SEED_IDENTITY_LEAK" if (
        checks["visible_state_contains_episode_id"] and checks["episode_id_literal_contains_seed"]
    ) else "PASS"
    payload = {
        "status": status,
        "scope": "STATIC_SOURCE_AND_PARSER_IMPORT_ONLY",
        "source_hashes": {
            "policies.py": sha(policies),
            "schema.py": sha(schema),
            "environment.py": sha(environment),
            "conditional.py": sha(conditional),
            "heldout_runner.py": sha(runner),
            "NEXT_HELDOUT_COMMAND.md": sha(next_command),
        },
        "checks": checks,
        "ordinary_policy_forbidden_attribute_hits": direct_attr_hits,
        "ordinary_policy_forbidden_import_hits": direct_import_hits,
        "actual_parser_help": help_text,
        "blocking_observation": "Policy code does not directly import latent modules, but VisibleState passes a literal seed-bearing episode_id, so interface-level leakage remains.",
        "required_repair_after_authorization": "Remove episode identity from policy projection; keep evaluator-private stream/pairing identity outside VisibleState.",
    }
    (OUT / "TOY_SIMULATOR_INFORMATION_FLOW_AUDIT.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(status)


if __name__ == "__main__":
    main()
