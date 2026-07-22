from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TESTS = Path(__file__).resolve().parent
CORPUS = TESTS / "metadata_videos"
MODEL = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
PROMPT = ROOT / "src/garc_eval/event_enumerate_v2/prompts/event_enumerate_v2.txt"


@pytest.fixture(scope="session")
def corpus_manifest():
    return json.loads((CORPUS / "CORPUS_MANIFEST.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def prompt_template():
    return PROMPT.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def local_processor():
    from transformers import AutoProcessor

    return AutoProcessor.from_pretrained(
        str(MODEL), trust_remote_code=True, local_files_only=True
    )
