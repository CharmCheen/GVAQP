#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path
raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name("run_scan_confirm_decision_benchmark.py")), "--phase", "baselines"]))

