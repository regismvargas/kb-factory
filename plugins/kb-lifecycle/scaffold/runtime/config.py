from __future__ import annotations

import copy
import json
import uuid

from .constants import LIFECYCLE_DEFAULTS
from .paths import CONFIG_PATH


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return {
        "schema_version": 1,
        "project": {"name": "My Project", "slug": "my-project", "kb_root": ".kb"},
        "domains": ["product", "architecture", "operations", "research"],
        "hot_session_limit": 12,
        "memory": {
            "now_path": "memory/NOW.md",
            "index_path": "memory/INDEX.md",
            "hot_path": "memory/HOT.md",
            "topics_dir": "memory/topics",
        },
        "exports": {
            "cowork_dir": "exports/cowork",
            "claude_ai_dir": "exports/claude-ai",
        },
        "retention": {
            "premise_review_days": 14,
            "hot_review_days": 7,
            "cold_after_days": 90,
        },
        "lifecycle": copy.deepcopy(LIFECYCLE_DEFAULTS),
    }


def write_config(config: dict) -> None:
    """Atomically replace kb.config.json, preserving key order and every key."""
    tmp = CONFIG_PATH.with_name(f".{CONFIG_PATH.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(CONFIG_PATH)
    finally:
        if tmp.exists():
            tmp.unlink()
