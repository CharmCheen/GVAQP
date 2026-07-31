import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def environment():
    value = os.environ.copy()
    value["PYTHONPATH"] = str(ROOT / "src")
    return value


def test_scan_cli_smoke(tmp_path):
    output = tmp_path / "scan.json"
    run = subprocess.run([sys.executable, "scripts/run_safe_coverage_scan.py", "--video-manifest",
                          "examples/example_video_manifest.json", "--max-actions", "3", "--output", str(output)],
                         cwd=ROOT, env=environment(), capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert [row["unit_id"] for row in json.loads(output.read_text())["actions"]] == ["2", "0", "4"]


def test_fixed_ratio_cli_smoke_without_oracle(tmp_path):
    run = subprocess.run([sys.executable, "scripts/run_fixed_ratio_controller.py", "--video-manifest",
                          "examples/example_video_manifest.json", "--query-config", "configs/example_query.yaml",
                          "--budget-sec", "20", "--config", "configs/fixed_ratio_25_75.yaml",
                          "--output-dir", str(tmp_path / "out")], cwd=ROOT, env=environment(),
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    summary = json.loads((tmp_path / "out/summary.json").read_text())
    durable = json.loads((tmp_path / "out/durable_result.json").read_text())
    assert summary["policy"] == "R4_FIXED_TIME_RATIO_25_75"
    assert durable["status"] == "FINAL" and durable["final_result"] == summary
