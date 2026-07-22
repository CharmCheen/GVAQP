import importlib.util
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts/evaluate_gate_a.py"
spec = importlib.util.spec_from_file_location("evaluate_gate_a", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GateAEvaluatorTests(unittest.TestCase):
    def test_perfect_and_inverse_auroc(self):
        units = [0, 1, 2, 3]
        labels = {0: False, 1: False, 2: True, 3: True}
        perfect = {0: 0.0, 1: 0.1, 2: 0.9, 3: 1.0}
        inverse = {unit: -score for unit, score in perfect.items()}
        self.assertEqual(module.auroc(labels, perfect, units), 1.0)
        self.assertEqual(module.auroc(labels, inverse, units), 0.0)

    def test_perfect_average_precision(self):
        units = [0, 1, 2, 3]
        labels = {0: False, 1: True, 2: False, 3: True}
        scores = {0: 0.1, 1: 0.9, 2: 0.0, 3: 1.0}
        self.assertEqual(module.average_precision(labels, scores, units), 1.0)

    def test_final_mode_requires_exact_frozen_signals_and_metadata(self):
        config = json.loads((PACKAGE / "config/gate_a_frozen.json").read_text())
        units = [0, 1]
        rows = []
        for signal, method in config["methods"].items():
            for unit in units:
                rows.append({
                    "signal_id": signal,
                    "unit_id": unit,
                    "score": float(unit),
                    "model_id": method["model_id"],
                    "model_revision": method["revision"],
                    "prompt_id": method["prompt_id"],
                })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scores.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            _, scores, _ = module.load_scores(path, config, units, final_mode=True)
            self.assertEqual(set(scores), set(config["methods"]))
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows[:-2])
            with self.assertRaises(ValueError):
                module.load_scores(path, config, units, final_mode=True)


if __name__ == "__main__":
    unittest.main()
