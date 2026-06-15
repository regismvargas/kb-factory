from __future__ import annotations

import json

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
        "lifecycle": LIFECYCLE_DEFAULTS,
    }
